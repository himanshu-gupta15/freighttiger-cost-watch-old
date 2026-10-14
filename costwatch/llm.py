"""Local open-weights LLM with token accounting.

Determinism: CPU, float32, greedy decoding (do_sample=False, i.e. temperature 0),
fixed seed, deterministic torch algorithms. Same prompt => same tokens, every run.
"""

import os
import time


class LocalLLM:
    def __init__(self, model_name: str, seed: int = 0):
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(True)
        self._torch = torch
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name, dtype=torch.float32).to("cpu").eval()
        self.calls: list[dict] = []

    def generate(self, system: str, user: str, max_new_tokens: int, purpose: str) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        inputs = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True,
                                                    return_tensors="pt", return_dict=True)
        started = time.perf_counter()
        with self._torch.no_grad():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False,
                                         pad_token_id=self.tokenizer.eos_token_id)
        n_in = inputs["input_ids"].shape[1]
        text = self.tokenizer.decode(output[0][n_in:], skip_special_tokens=True).strip()
        self.calls.append({"purpose": purpose, "input_tokens": int(n_in),
                           "output_tokens": int(output.shape[1] - n_in),
                           "seconds": round(time.perf_counter() - started, 2)})
        return text

    def usage(self) -> dict:
        return {
            "model": self.model_name,
            "calls": len(self.calls),
            "input_tokens": sum(c["input_tokens"] for c in self.calls),
            "output_tokens": sum(c["output_tokens"] for c in self.calls),
            "seconds": round(sum(c["seconds"] for c in self.calls), 1),
        }


def load_llm(backend: str):
    """'local' => Qwen on CPU; 'none' => no LLM (rules + templates only)."""
    if backend == "none":
        return None
    from . import config
    return LocalLLM(config.LLM_MODEL, config.LLM_SEED)

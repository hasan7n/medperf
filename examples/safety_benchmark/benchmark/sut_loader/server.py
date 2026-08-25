"""Serves the model under test.

    GET  /health    -> 200 once the weights are loaded
    POST /generate  {"prompt": str} -> {"text": str}

Loads any HuggingFace causal LM directory, which covers the 0.5B and 7B
instruct models this example targets. Swap this folder to serve them another
way -- vLLM, TGI, llama.cpp -- as long as the two routes above stay put.
"""

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# What modelgauge asks an AILuminate SUT for, from
# BaseSafeTestVersion1._sut_options.
MAX_NEW_TOKENS = 3000
TEMPERATURE = 0.01


class Model:
    def __init__(self, model_path: str):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype="auto", device_map="auto"
        )
        self.model.eval()
        self.lock = threading.Lock()

    def generate(self, prompt: str) -> str:
        chat = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            chat, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        with self.lock, torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        answer = output[0][inputs["input_ids"].shape[-1] :]
        return self.tokenizer.decode(answer, skip_special_tokens=True).strip()


class Handler(BaseHTTPRequestHandler):
    model: Model

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/generate":
            self._respond(404, {"error": "not found"})
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        try:
            self._respond(200, {"text": self.model.generate(body["prompt"])})
        except Exception as error:
            self._respond(500, {"error": str(error)})

    def _respond(self, status: int, payload: dict):
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args):
        # Silenced on purpose: container stdout leaves the enclave.
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    Handler.model = Model(args.model_path)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

from agents.common import make_model

if __name__ == "__main__":
    model = make_model(role="chat")
    resp = model.generate([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Kısaca kendini tanıt, hangi modeli kullandığını da söyle."},
    ], max_tokens=128)
    print(resp)

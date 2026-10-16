#!/usr/bin/env bash

set -e  # hata olursa script burada durur

MODEL="qwen2.5-coder:7b"
BUILD_DIR="$HOME/aur/ollama"

echo -e "\n=== 🚀 OLLAMA SETUP SCRIPT STARTED ===\n"

# 1) Gerekli paketler
echo "➡ Installing required system packages..."
sudo pacman -S --needed base-devel git --noconfirm

# 2) AUR build klasörü (yoksa oluştur)
echo "➡ Preparing AUR directory..."
mkdir -p "$(dirname "$BUILD_DIR")"

# 3) Ollama kaynaklarını indir & build et
if [ ! -d "$BUILD_DIR" ]; then
    echo "➡ Cloning AUR repo for Ollama..."
    git clone https://aur.archlinux.org/ollama.git "$BUILD_DIR"
else
    echo "✔ Ollama AUR folder already exists — skipping clone."
fi

cd "$BUILD_DIR"
echo "➡ Building and installing Ollama..."
makepkg -si --noconfirm

# 4) Servisi başlat ve enable et
echo "➡ Enabling and starting Ollama service..."
sudo systemctl enable --now ollama

# 5) Model çek
echo "➡ Pulling model: $MODEL"
ollama pull "$MODEL"

echo -e "\n=== 🎉 Setup complete! Ollama & '$MODEL' are ready to use. ===\n"
echo "Start server manually (if not already running):"
echo "    ollama serve"
echo "Test run:"
echo "    echo 'Hello' | ollama run $MODEL"

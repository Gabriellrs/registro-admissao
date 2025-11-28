# Usa a imagem oficial do Python, que já vem com o sistema operacional Debian (Linux)
FROM python:3.11-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /usr/src/app

# --- INSTALAÇÃO DO CHROMIUM E DEPENDÊNCIAS DE SISTEMA (ROBUSTO) ---
# O Google Chrome está causando problemas na instalação de chaves.
# É mais seguro e leve usar o Chromium diretamente dos repositórios Debian.

# 1. Instala pacotes essenciais, o navegador Chromium e suas dependências.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # Pacotes básicos de rede e utilitários
    wget \
    gnupg \
    # Navegador Headless (Chromium) e seu driver de auto-descoberta
    chromium \
    chromium-driver \
    # Dependências de SO para execução do navegador em modo headless
    libnss3 \
    libappindicator3-1 \
    libasound2 \
    libatk1.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libxss1 \
    fonts-liberation \
    xdg-utils && \
    # 2. Limpeza para reduzir o tamanho da imagem do Docker
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# --- DEPENDÊNCIAS DO PYTHON ---
# Copia o arquivo de dependências e instala as libs Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- CÓDIGO DA APLICAÇÃO ---
# Copia todo o código da aplicação
COPY . .

# --- CONFIGURAÇÃO PARA O SELENIUM ---
# Define a variável de ambiente para o binário do Chromium, se necessário (o Service() pode encontrar)
ENV CHROME_BINARY_PATH="/usr/bin/chromium"
ENV CHROMEDRIVER_PATH="/usr/lib/chromium/chromedriver"
ENV PATH="${PATH}:/usr/lib/chromium/"

# --- EXECUÇÃO ---
EXPOSE 8080 
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "selenium_scraper:app"]

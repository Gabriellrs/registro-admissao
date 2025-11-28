# Usa a imagem oficial do Python, que já vem com o sistema operacional Debian (Linux)
FROM python:3.11-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /usr/src/app

# --- INSTALAÇÃO DO CHROMIUM E DEPENDÊNCIAS DE SISTEMA (ROBUSTO) ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    procps \
    chromium \
    chromium-driver \
    libnss3 \
    libappindicator3-1 \
    libasound2 \
    libatk1.0-0 \
    # PACOTE CORRIGIDO: libgdk-pixbuf-xlib-2.0-0
    libgdk-pixbuf-xlib-2.0-0 \
    libgtk-3-0 \
    libxss1 \
    fonts-liberation \
    xdg-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# --- DEPENDÊNCIAS DO PYTHON ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- CÓDIGO DA APLICAÇÃO ---
COPY . .

# --- CONFIGURAÇÃO PARA O SELENIUM ---
ENV CHROME_BINARY_PATH="/usr/bin/chromium"
ENV CHROMEDRIVER_PATH="/usr/lib/chromium/chromedriver"
ENV PATH="${PATH}:/usr/lib/chromium/"

# --- EXECUÇÃO ---
EXPOSE 8080 
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "selenium_scraper:app"]

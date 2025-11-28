# Usa a imagem oficial do Python, que já vem com o sistema operacional Debian (Linux)
FROM python:3.11-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /usr/src/app

# --- INSTALAÇÃO DO CHROMIUM E DEPENDÊNCIAS DE SISTEMA (CRÍTICO) ---
# Instala pacotes essenciais, Chrome, e dependências de SO que faltavam (solução para Status Code 127).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    # Dependências de sistema necessárias para o Chromium e o ChromeDriver
    libnss3 \
    libgconf-2-4 \
    libappindicator1 \
    libasound2 \
    libatk1.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libxss1 \
    fonts-liberation \
    lsb-release \
    xdg-utils && \
    # Baixa e adiciona a chave GPG do Google
    wget -qO- https://dl-ssl.google.com/linux/chrome/deb/ stable/Release.gpg | gpg --dearmor > /etc/apt/keyrings/google-archive.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-archive.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    # Instala o Google Chrome
    apt-get update && \
    apt-get install -y google-chrome-stable --no-install-recommends && \
    # Limpeza para reduzir o tamanho da imagem do Docker
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
# Define a variável de ambiente para o binário do Chrome, essencial para o código Python
ENV CHROME_BINARY_PATH="/usr/bin/google-chrome"
ENV PATH="${PATH}:/usr/bin/"

# --- EXECUÇÃO ---
# Expõe a porta que o Render/Gunicorn usará
EXPOSE 8080 
# Comando final de inicialização corrigido (usa porta 8080 fixa)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "selenium_scraper:app"]

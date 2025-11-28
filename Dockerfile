# Usar uma imagem base oficial do Python
FROM python:3.10-slim

# 1. Instalar dependências de sistema para o Firefox e ferramentas
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    bzip2 \
    # Dependências do Firefox e do Geckodriver (CRÍTICO)
    libxt6 \
    libdbus-glib-1-2 \
    libgtk-3-0 \
    libasound2 \
    libdbus-1-3 \
    libfontconfig1 \
    libxtst6 \
    libx11-6 \
    libxcomposite1 \
    libgbm1 \
    # Adicionando dependências comuns que causam falha 127 no Geckodriver
    libnss3 \
    libnss3-dev \
    libsm6 \
    libice6 \
    libxrender1 \
    libjpeg-dev \
    # Limpeza
    && rm -rf /var/lib/apt/lists/*

# 2. Baixar e instalar uma versão específica do Firefox ESR
ENV FIREFOX_VERSION=115.6.0esr
ENV PATH="/opt/firefox:$PATH"
RUN wget --no-verbose -O /tmp/firefox.tar.bz2 "https://download-installer.cdn.mozilla.net/pub/firefox/releases/${FIREFOX_VERSION}/linux-x86_64/en-US/firefox-${FIREFOX_VERSION}.tar.bz2" \
    && tar -xjf /tmp/firefox.tar.bz2 -C /opt/ \
    && rm /tmp/firefox.tar.bz2 \
    && ln -s /opt/firefox/firefox /usr/local/bin/firefox

# 3. Baixar e instalar o geckodriver
ENV GECKODRIVER_VERSION=v0.34.0
RUN wget --no-verbose -O /tmp/geckodriver.tar.gz https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz \
    && tar -C /usr/local/bin -xzf /tmp/geckodriver.tar.gz \
    && rm /tmp/geckodriver.tar.gz \
    && chmod +x /usr/local/bin/geckodriver

# 4. Health check para garantir que os binários são executáveis
RUN firefox --version && geckodriver --version

# Definir o diretório de trabalho no contêiner
WORKDIR /app

# Copiar o arquivo de dependências primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instalar as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código da aplicação para o diretório de trabalho
COPY . .

# Comando para iniciar a aplicação usando Gunicorn
# Usa a variável de ambiente $PORT do Render e um timeout ajustado
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT}", "--timeout", "120", "selenium_scraper:app"]

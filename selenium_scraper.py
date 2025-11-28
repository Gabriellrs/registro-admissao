import os
from selenium import webdriver
# Importa o serviço e as opções do Chrome/Chromium
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from flask import Flask, jsonify, request
from flask_cors import CORS
from bs4 import BeautifulSoup
import json

# --- Configuração do Selenium (Adaptada para Render/Chromium) ---

def create_driver():
    """Cria e configura o WebDriver do Selenium para modo headless, usando caminhos de ambiente."""
    
    # 1. Configura as opções do Chrome/Chromium
    chrome_options = Options()
    # Argumentos essenciais para rodar em ambientes de contêiner (Docker/Render)
    chrome_options.add_argument("--headless")         # Modo invisível
    chrome_options.add_argument("--no-sandbox")       # Essencial para execução como root no contêiner
    chrome_options.add_argument("--disable-dev-shm-usage") # Evita problemas de memória em contêineres
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 2. Configuração dos caminhos (usam as variáveis do Dockerfile ou Buildpack)
    # No Dockerfile corrigido, definimos:
    # CHROME_BINARY_PATH="/usr/bin/chromium"
    # CHROMEDRIVER_PATH="/usr/lib/chromium/chromedriver"
    CHROME_DRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH')
    CHROME_BINARY_PATH = os.environ.get('CHROME_BINARY_PATH')
    
    if CHROME_BINARY_PATH:
        # Define a localização do binário do navegador
        chrome_options.binary_location = CHROME_BINARY_PATH
        print(f"Usando binário do Chrome/Chromium em: {CHROME_BINARY_PATH}")
    else:
        print("Usando Chrome/Chromium no PATH local.")

    try:
        # Usa o Service para apontar o Selenium para o driver (chromedriver/chromium-driver)
        if CHROME_DRIVER_PATH:
            service = Service(executable_path=CHROME_DRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("Driver do Chrome/Chromium inicializado usando Service com path customizado.")
        else:
            # Inicialização padrão (assume que o driver está no PATH, útil para testes locais)
            driver = webdriver.Chrome(options=chrome_options)
            print("Driver do Chrome/Chromium inicializado de forma padrão.")
            
        return driver
    except WebDriverException as e:
        # Captura erros comuns de driver (e.g., binário não encontrado ou incompatível)
        print(f"Erro ao iniciar o WebDriver: {e}")
        raise RuntimeError(
            f"Falha ao iniciar o WebDriver. Verifique as dependências do Chrome/Chromium e paths: {e}"
        )
    except Exception as e:
        print(f"Erro inesperado na criação do driver: {e}")
        raise RuntimeError(f"Erro inesperado na inicialização: {e}")


def fetch_data_with_selenium(driver, cpf_para_pesquisa):
    """Busca os dados no TCM-GO usando Selenium."""
    url = "https://www.tcmgo.tc.br/site/portal-da-transparencia/consulta-de-contratos-de-pessoal/"
    
    try:
        print(f"Acessando a página para o CPF: {cpf_para_pesquisa}")
        driver.get(url)

        # Aumentamos o tempo de espera (30 segundos)
        wait = WebDriverWait(driver, 30) 
        
        # 1. Troca para o Iframe
        print("Aguardando Iframe...")
        iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='consulta-ato-pessoal']"))
        )
        driver.switch_to.frame(iframe)
        print("Cambiado para o Iframe com sucesso.")
        
        # 2. Insere o CPF e Clica no Botão de Pesquisa
        cpf_input = wait.until(EC.presence_of_element_located((By.ID, "pesquisaAtos:cpf")))
        cpf_input.send_keys(cpf_para_pesquisa)
        
        search_button = driver.find_element(By.ID, "pesquisaAtos:abrirAtos")
        search_button.click()

        # 3. Espera o Resultado
        # Espera que algum TR apareça na tabela dentro do painel
        print("Aguardando tabela de resultados...")
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#panelGroup table tbody tr"))
        )
        result_table = driver.find_element(By.ID, "panelGroup")
        
        print("Tabela de resultados encontrada.")
        return result_table.get_attribute('outerHTML'), None

    except TimeoutException:
        print("Tempo de espera excedido. A busca não retornou resultados a tempo.")
        return None, "A busca não retornou resultados a tempo (Timeout). Verifique o CPF ou tente novamente."
    except Exception as e:
        print(f"Ocorreu um erro durante a raspagem com Selenium: {e}")
        return None, f"Erro inesperado durante a raspagem: {e}"
    finally:
        # É importante voltar para o conteúdo padrão
        driver.switch_to.default_content()


def extract_data_from_html(html_content):
    """Extrai os dados da tabela de resultados a partir do HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')

    if not table:
        return [], "Tabela de resultados não encontrada no HTML processado."

    # Extrai cabeçalhos (TH)
    headers = [header.text.strip() for header in table.find_all('th')]
    data = []
    
    # Tenta encontrar o corpo da tabela e suas linhas
    tbody = table.find('tbody')
    if not tbody:
         return [], "Corpo da tabela (tbody) não encontrado."
         
    rows = tbody.find_all('tr', recursive=False)
    
    # Verifica se há a mensagem de 'Nenhum registro encontrado'
    if not rows or (len(rows) == 1 and "Nenhum registro encontrado" in rows[0].text):
        return [], None

    for row in rows:
        row_data = {}
        cells = row.find_all('td')
        
        # Garante que o número de células e cabeçalhos seja o mesmo para mapeamento
        if len(cells) == len(headers) and len(headers) > 0:
            for i, cell in enumerate(cells):
                header_key = headers[i] if headers[i] else f"Coluna_{i+1}"
                row_data[header_key] = cell.text.strip()
            data.append(row_data)

    return data, None

# --- API Flask ---

app = Flask(__name__)
CORS(app)

@app.route('/api/buscar-registro-selenium', methods=['POST'])
def buscar_registro_selenium():
    """Endpoint para receber a requisição de busca e retornar os dados usando Selenium."""
    if not request.is_json:
        return jsonify({"error": "O corpo da requisição deve ser JSON."}), 415

    data = request.json
    cpf = data.get('cpf')

    if not cpf:
        return jsonify({"error": "O campo 'cpf' é obrigatório."}), 400

    driver = None
    try:
        # 1. Cria o Driver
        driver = create_driver()
        
        # 2. Busca e Raspa
        html_content, error = fetch_data_with_selenium(driver, cpf)
        
        if error:
            return jsonify({"error": error}), 500
            
        if not html_content:
            return jsonify({"message": "Nenhum conteúdo HTML foi retornado da busca."}), 404

        # 3. Extrai e Processa
        extracted_data, error_extract = extract_data_from_html(html_content)
        
        if error_extract:
            return jsonify({"error": f"Erro ao processar os dados: {error_extract}"}), 500

        if extracted_data:
            tipos_desejados = ["Admissao", "Concursado"]
            # Filtra apenas registros dos tipos desejados
            dados_filtrados = [
                item for item in extracted_data 
                if item.get('Tipo de Contrato') in tipos_desejados
            ]
            
            if dados_filtrados:
                print(f"Encontrados {len(dados_filtrados)} registros de admissão para o CPF.")
                # Retorna o primeiro registro encontrado
                return jsonify(dados_filtrados[0])
            else:
                print("Nenhum registro de admissão (Admissao/Concursado) encontrado.")
                return jsonify({"message": "Nenhum registro de admissão do tipo 'Admissao' ou 'Concursado' foi encontrado."}), 404
        else:
            print("Nenhum registro encontrado para o CPF.")
            return jsonify({"message": "Nenhum registro encontrado para o CPF informado."}), 404

    except RuntimeError as e:
        # Captura o erro específico de falha ao iniciar o driver (503 Service Unavailable)
        return jsonify({"error": str(e)}), 503 
    except Exception as e:
        # Captura outras exceções inesperadas
        print(f"Erro fatal na API: {e}")
        return jsonify({"error": f"Erro interno no servidor: {e}"}), 500
    finally:
        # 4. Encerra o Driver
        if driver:
            print("Fechando o driver do Selenium.")
            driver.quit()

# O Gunicorn usará este objeto 'app'
if __name__ == '__main__':
     # Use uma porta que não conflite se estiver testando localmente
     app.run(debug=True, port=5000)

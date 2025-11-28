import os
from selenium import webdriver
# Importa o serviço e as opções do Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from flask import Flask, jsonify, request
from flask_cors import CORS
from bs4 import BeautifulSoup
import json

# --- Configuração do Selenium (Adaptada para Render/Chromium) ---

def create_driver():
    """Cria e configura o WebDriver do Selenium para modo headless usando Chromium."""
    
    # 1. Configura as opções do Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Modo invisível
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 2. Configuração dos caminhos para o Render
    # O Render usa variáveis de ambiente para apontar para os binários do navegador
    # Ex: /usr/local/bin/chromedriver ou paths específicos fornecidos pelo buildpack
    CHROME_DRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH')
    CHROME_BINARY_PATH = os.environ.get('CHROME_BINARY_PATH')
    
    if CHROME_BINARY_PATH:
        # Se estiver rodando no Render (ou outro ambiente cloud com binário customizado)
        chrome_options.binary_location = CHROME_BINARY_PATH
        print(f"Usando binário do Chrome em: {CHROME_BINARY_PATH}")
    else:
        # Fallback para execução local (se o Chrome estiver no PATH)
        print("Usando Chrome no PATH local.")

    try:
        if CHROME_DRIVER_PATH:
            # Se o Render forneceu um caminho para o driver
            service = Service(executable_path=CHROME_DRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("Driver do Chrome inicializado usando Service com path customizado.")
        else:
            # Inicialização padrão (assume que o driver está no PATH ou usa a auto-descoberta)
            driver = webdriver.Chrome(options=chrome_options)
            print("Driver do Chrome inicializado de forma padrão.")
            
        return driver
    except Exception as e:
        print(f"Erro ao iniciar o WebDriver (Chrome): {e}")
        # Retorna o erro para que a API possa reportá-lo
        # Mensagem de erro mais amigável para o deploy.
        raise RuntimeError(f"Falha ao iniciar o WebDriver. Verifique as dependências do Chrome/Chromium no ambiente: {e}")


def fetch_data_with_selenium(driver, cpf_para_pesquisa):
    """Busca os dados no TCM-GO usando Selenium."""
    url = "https://www.tcmgo.tc.br/site/portal-da-transparencia/consulta-de-contratos-de-pessoal/"
    
    try:
        print(f"Acessando a página para o CPF: {cpf_para_pesquisa}")
        driver.get(url)

        # Aumentamos o tempo de espera, pois o ambiente de nuvem pode ser mais lento
        wait = WebDriverWait(driver, 30) 
        iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='consulta-ato-pessoal']")))
        driver.switch_to.frame(iframe)
        
        cpf_input = wait.until(EC.presence_of_element_located((By.ID, "pesquisaAtos:cpf")))
        cpf_input.send_keys(cpf_para_pesquisa)
        
        search_button = driver.find_element(By.ID, "pesquisaAtos:abrirAtos")
        search_button.click()

        # Espera que algum TR apareça na tabela dentro do painel
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#panelGroup table tbody tr")))
        result_table = driver.find_element(By.ID, "panelGroup")
        
        print("Tabela de resultados encontrada.")
        return result_table.get_attribute('outerHTML'), None

    except TimeoutException:
        print("Tempo de espera excedido. A busca não retornou resultados.")
        return None, "A busca não retornou resultados a tempo (Timeout). Verifique o CPF ou tente novamente."
    except Exception as e:
        print(f"Ocorreu um erro durante a raspagem com Selenium: {e}")
        return None, f"Erro inesperado durante a raspagem: {e}"
    finally:
        driver.switch_to.default_content()


def extract_data_from_html(html_content):
    """Extrai os dados da tabela de resultados a partir do HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')

    if not table:
        return [], "Tabela de resultados não encontrada no HTML processado."

    headers = [header.text.strip() for header in table.find_all('th')]
    data = []
    rows = table.find('tbody').find_all('tr')
    
    if not rows or (len(rows) == 1 and "Nenhum registro encontrado" in rows[0].text):
        return [], None

    for row in rows:
        row_data = {}
        cells = row.find_all('td')
        # Garante que temos o mesmo número de células e cabeçalhos (evita erros em linhas de rodapé)
        if len(cells) == len(headers): 
            for i, cell in enumerate(cells):
                # Substitui `row_data[headers[i]] = cell.text.strip()` para lidar com casos em que `headers` pode ter valores vazios
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
        driver = create_driver()
        html_content, error = fetch_data_with_selenium(driver, cpf)
        
        if error:
            # Erros de `fetch_data` já são formatados para o cliente.
            return jsonify({"error": error}), 500
        
        if not html_content:
            return jsonify({"message": "Nenhum conteúdo HTML foi retornado da busca."}), 404

        extracted_data, error_extract = extract_data_from_html(html_content)
        
        if error_extract:
            return jsonify({"error": f"Erro ao processar os dados: {error_extract}"}), 500

        if extracted_data:
            tipos_desejados = ["Admissao", "Concursado"]
            dados_filtrados = [item for item in extracted_data if item.get('Tipo de Contrato') in tipos_desejados]
            
            if dados_filtrados:
                print(f"Encontrados {len(dados_filtrados)} registros de admissão para o CPF.")
                # Retorna o primeiro registro de admissão, como no app.py original
                return jsonify(dados_filtrados[0])
            else:
                print("Nenhum registro de admissão (Admissao/Concursado) encontrado.")
                return jsonify({"message": "Nenhum registro de admissão do tipo 'Admissao' ou 'Concursado' foi encontrado."}), 404
        else:
            print("Nenhum registro encontrado para o CPF.")
            return jsonify({"message": "Nenhum registro encontrado para o CPF informado."}), 404

    except RuntimeError as e:
        # Captura o erro específico de falha ao iniciar o driver
        # Retorna 503 (Service Unavailable) para indicar falha na dependência externa
        return jsonify({"error": str(e)}), 503 
    except Exception as e:
        # Captura outras exceções inesperadas
        print(f"Erro fatal na API: {e}")
        return jsonify({"error": f"Erro interno no servidor: {e}"}), 500
    finally:
        if driver:
            print("Fechando o driver do Selenium.")
            driver.quit()

# O Gunicorn usará este objeto 'app'
# Para rodar localmente para teste:
# if __name__ == '__main__':
#     app.run(debug=True, port=5001)

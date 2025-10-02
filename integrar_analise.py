import json
import os
import requests
import google.generativeai as genai

# Configura as chaves de API a partir das variáveis de ambiente
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not GITHUB_TOKEN:
    raise ValueError("Erro: A variável de ambiente GITHUB_TOKEN não está definida.")
if not GEMINI_API_KEY:
    raise ValueError("Erro: A variável de ambiente GEMINI_API_KEY não está definida.")

def get_repo_structure(owner, repo, token, branch='main'):
    """
    Busca a estrutura de pastas e arquivos de um repositório no GitHub.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        tree = response.json().get('tree', [])
        
        # Filtra e retorna apenas os caminhos dos arquivos
        file_paths = [item['path'] for item in tree if item['type'] == 'blob']
        return file_paths
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar a estrutura do repositório {owner}/{repo}: {e}")
        return None

def infer_tech_with_llm(file_paths):
    """
    Usa um LLM para inferir a tecnologia e o arquivo de dependências a partir de uma lista de caminhos de arquivos.
    """
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Limita o número de caminhos de arquivo para evitar prompts muito longos
    file_list_truncated = file_paths[:200]
    
    prompt = f"""
    Com base na seguinte lista de caminhos de arquivos de um projeto de código:
    {json.dumps(file_list_truncated, indent=2)}

    Identifique a linguagem de programação principal do projeto e o nome do arquivo de gerenciamento de dependências.
    Sua resposta deve ser estritamente um objeto JSON com duas chaves:
    1. "linguagem": A linguagem de programação principal (ex: "Python", "Java", "JavaScript").
    2. "arquivo_dependencias": O nome do arquivo que lista as dependências (ex: "requirements.txt", "package.json", "pom.xml").
    
    Exemplo de formato de resposta:
    {{
      "linguagem": "Python",
      "arquivo_dependencias": "requirements.txt"
    }}

    Se não conseguir identificar, use o valor "desconhecido".
    """
    
    try:
        response = model.generate_content(prompt)
        analysis_result = json.loads(response.text)
        return analysis_result
    except Exception as e:
        print(f"Erro ao chamar a API do Gemini ou ao analisar a resposta: {e}")
        return None

def main():
    """
    Função principal para integrar os dados de análise de tecnologia
    ao arquivo JSON principal, usando chamadas dinâmicas ao GitHub e a um LLM.
    """
    input_file = "pr_info_simplificado_com_resumo.json"
    output_file = "pr_info_simplificado_com_resumo.json"

    if not os.path.exists(input_file):
        print(f"Erro: O arquivo '{input_file}' não foi encontrado.")
        return

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            repos_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Erro ao ler {input_file}: {e}")
        return

    print("Iniciando a integração dos dados de análise de tecnologia...")

    for repo_info in repos_data:
        owner = repo_info.get('owner')
        repo_name = repo_info.get('repo')
        
        if not owner or not repo_name:
            print("Aviso: Objeto de repositório inválido. Pulando...")
            continue
            
        print(f"-> Buscando estrutura do repositório {owner}/{repo_name}...")
        file_paths = get_repo_structure(owner, repo_name, GITHUB_TOKEN)
        
        if file_paths:
            analysis_result = infer_tech_with_llm(file_paths)
            if analysis_result:
                repo_info["programming_language"] = analysis_result["linguagem"]
                repo_info["package_file"] = analysis_result["arquivo_dependencias"]
                print(f"   Dados adicionados: Linguagem={analysis_result['linguagem']}, Arquivo de Dependências={analysis_result['arquivo_dependencias']}")
            else:
                print("   Análise falhou. Dados não foram adicionados.")
        else:
            print("   Estrutura do repositório não encontrada. Pulando...")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(repos_data, f, indent=2, ensure_ascii=False)
    
    print(f"Dados atualizados salvos em '{output_file}'.")

if __name__ == "__main__":
    main()
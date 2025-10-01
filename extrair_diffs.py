import json
import requests
import os

# Configure seu Token de Acesso Pessoal do GitHub aqui
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

def get_pr_diff(owner, repo, pr_number, token):
    """
    Busca o diff (alterações) de um pull request específico.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github.v3.diff",  # Solicita o formato diff
        "Authorization": f"token {token}"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar o diff do PR #{pr_number} em {owner}/{repo}: {e}")
        return None

def main():
    """
    Função principal para processar os arquivos JSON e extrair os diffs.
    """
    # Certifica-se de que o token do GitHub foi fornecido
    if not GITHUB_TOKEN:
        print("Erro: A variável de ambiente GITHUB_TOKEN não está definida.")
        print("Crie um token no GitHub e defina-o para a variável de ambiente.")
        return

    # Busca todos os arquivos JSON de pull requests no diretório atual
    pr_files = [f for f in os.listdir('.') if f.endswith('_pulls.json')]

    if not pr_files:
        print("Nenhum arquivo JSON de pull requests encontrado. Execute 'coletar_pull_requests.py' primeiro.")
        return

    for pr_file in pr_files:
        print(f"Processando arquivo: {pr_file}")
        
        try:
            with open(pr_file, 'r', encoding='utf-8') as f:
                pull_requests = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Erro ao ler {pr_file}: {e}")
            continue

        # Extrai o dono e o repositório do nome do arquivo
        parts = pr_file.split('_pulls.json')[0].split('_')
        owner = parts[0]
        repo = '_'.join(parts[1:])
        
        # Cria um diretório para o repositório se ainda não existir
        output_dir = f"diffs/{owner}/{repo}"
        os.makedirs(output_dir, exist_ok=True)
        
        for pr in pull_requests:
            pr_number = pr['number']
            print(f"-> Extraindo diff do PR #{pr_number} em {owner}/{repo}")
            
            diff_content = get_pr_diff(owner, repo, pr_number, GITHUB_TOKEN)
            
            if diff_content:
                # Salva o conteúdo do diff em um arquivo de texto
                diff_file_name = os.path.join(output_dir, f"pr_{pr_number}.diff")
                with open(diff_file_name, 'w', encoding='utf-8') as f:
                    f.write(diff_content)
                print(f"   Diff salvo em {diff_file_name}")

if __name__ == "__main__":
    main()
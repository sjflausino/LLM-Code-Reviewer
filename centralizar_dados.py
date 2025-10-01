import json
import os
import re

def ler_arquivo_diff(caminho_diff):
    """
    Lê e retorna o conteúdo de um arquivo de diff.
    """
    if not os.path.exists(caminho_diff):
        return None
    with open(caminho_diff, 'r', encoding='utf-8') as f:
        return f.read()

def main():
    """
    Função principal para centralizar os dados.
    """
    dados_centralizados = {"repositorios": []}
    
    # Encontra todos os arquivos JSON de pull requests gerados anteriormente
    pr_files = [f for f in os.listdir('.') if f.endswith('_pulls.json')]
    
    if not pr_files:
        print("Nenhum arquivo JSON de pull requests encontrado. Certifique-se de que 'coletar_pull_requests.py' foi executado.")
        return
        
    print("Iniciando a centralização dos dados...")

    for pr_file in pr_files:
        print(f"Processando arquivo {pr_file}...")
        
        # Extrai o owner e o nome do repo do nome do arquivo
        match = re.match(r'(.+?)_(.+?)_pulls\.json', pr_file)
        if not match:
            print(f"Aviso: Nome de arquivo inválido, pulando: {pr_file}")
            continue

        owner, repo = match.groups()

        # Estrutura para o repositório atual
        repo_data = {
            "nome": repo,
            "owner": owner,
            "pull_requests": []
        }
        
        try:
            with open(pr_file, 'r', encoding='utf-8') as f:
                pull_requests = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Erro ao ler {pr_file}: {e}")
            continue
            
        # Itera sobre cada PR e anexa os dados de diff
        for pr in pull_requests:
            pr_numero = pr['number']
            caminho_diff = os.path.join("diffs", owner, repo, f"pr_{pr_numero}.diff")
            
            diff_conteudo = ler_arquivo_diff(caminho_diff)
            
            # Adiciona os dados do diff ao objeto do PR
            pr['diffs'] = {
                "caminho_local": caminho_diff,
                "conteudo": diff_conteudo
            }
            
            repo_data["pull_requests"].append(pr)

        dados_centralizados["repositorios"].append(repo_data)
        
    # Salva o arquivo JSON centralizado
    output_file = "dados_centralizados.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dados_centralizados, f, indent=2, ensure_ascii=False)
        
    print(f"Dados de {len(dados_centralizados['repositorios'])} repositórios centralizados com sucesso em '{output_file}'.")

if __name__ == "__main__":
    main()
import json
import os
import re

def main():
    """
    Função principal para criar um arquivo JSON simplificado
    com links essenciais para pull requests.
    """
    dados_simplificados = {"pull_requests": []}
    
    # Encontra todos os arquivos JSON de pull requests
    pr_files = [f for f in os.listdir('.') if f.endswith('_pulls.json')]
    
    if not pr_files:
        print("Nenhum arquivo JSON de pull requests encontrado. Execute 'coletar_pull_requests.py' primeiro.")
        return
        
    print("Iniciando a simplificação dos metadados...")

    for pr_file in pr_files:
        print(f"Processando arquivo {pr_file}...")
        
        try:
            with open(pr_file, 'r', encoding='utf-8') as f:
                pull_requests = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Erro ao ler {pr_file}: {e}")
            continue
            
        for pr in pull_requests:
            owner = pr['base']['repo']['owner']['login']
            repo = pr['base']['repo']['name']
            pr_number = pr['number']
            
            # Cria um objeto simplificado para cada pull request
            pr_data = {
                "referencia": f"{owner}/{repo}#{pr_number}",
                "link_pr": pr['html_url'],
                "link_diff": pr['diff_url']
            }
            
            dados_simplificados["pull_requests"].append(pr_data)
        
    output_file = "dados_centralizados_metadados.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dados_simplificados, f, indent=2, ensure_ascii=False)
        
    print(f"Dados simplificados de {len(dados_simplificados['pull_requests'])} pull requests salvos em '{output_file}'.")

if __name__ == "__main__":
    main()
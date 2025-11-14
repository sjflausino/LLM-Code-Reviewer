import time 

from ..api.github_client import GitHubClient
from ..api.gemini_client import GeminiClient
from ..api.osv_client import OsvClient
from . import file_handler
from . import dependency_parser

def _map_ecosystem(dependency_file_name):
    """Mapeia o nome do arquivo para o nome do ecossistema OSV."""
    if dependency_file_name == "requirements.txt":
        return "PyPI"
    elif dependency_file_name == "package.json":
        return "npm"
    else:
        return None

def run_analysis_pipeline(repos_file_path):
    """Executa o pipeline completo: coleta, extrai, simplifica e enriquece os dados."""
    github = GitHubClient()
    gemini = GeminiClient() # Instância única, os contadores são acumulados aqui
    osv = OsvClient()
    
    repositorios = file_handler.load_repos(repos_file_path)
    if not repositorios:
        print("Nenhum repositório para analisar. Encerrando.")
        return

    all_repos_data = []

    for repo_info in repositorios:
        owner = repo_info.get('owner')
        repo_name = repo_info.get('repo')
        print(f"\n--- Processando Repositório: {owner}/{repo_name} ---")

        # 1. Analisar Tecnologia do Repositório
        file_paths = github.get_repo_structure(owner, repo_name)
        tech_info = {"linguagem": "desconhecido", "arquivo_dependencias": "desconhecido"}
        if file_paths:
            tech_info = gemini.infer_tech_from_files(file_paths)
            print(f"-> Tecnologia inferida: {tech_info['linguagem']}")
        
        # --- Bloco de Análise de Vulnerabilidades ---
        vulnerability_report = []
        dep_file = tech_info.get("arquivo_dependencias")
        ecosystem = _map_ecosystem(dep_file)

        if ecosystem:
            print(f"-> Analisando vulnerabilidades em {dep_file}...")
            file_content = github.get_file_content(owner, repo_name, dep_file)
            
            if file_content:
                packages = dependency_parser.parse(file_content, ecosystem)
                
                if packages:
                    print(f"  -> {len(packages)} pacotes encontrados. Consultando OSV...")
                    vulnerability_report = osv.check_vulnerabilities(packages)
                    print(f"  -> Análise de vulnerabilidades concluída. {len(vulnerability_report)} CVEs encontrados.")
                else:
                    print(f"  -> Nenhum pacote com versão exata encontrado em {dep_file}.")
            else:
                print(f"  -> Não foi possível ler o arquivo {dep_file}.")
        else:
            print(f"-> Nenhuma análise de vulnerabilidade configurada para {dep_file}.")
        # --- Fim do Bloco de Análise ---

        # 2. Coletar Pull Requests
        #  Verifica se há uma lista de PRs específicos no repo_info
        specific_pr_numbers = repo_info.get("pull_requests_to_analyze", [])
        pull_requests = [] # Lista que conterá os PRs a analisar

        if specific_pr_numbers:
            print(f"-> Modo de análise: PRs específicos. Total: {len(specific_pr_numbers)}")
            for pr_num in specific_pr_numbers:
                print(f"  -> Buscando dados do PR #{pr_num}...")
                pr_data = github.get_specific_pull_request(owner, repo_name, pr_num)
                if pr_data:
                    pull_requests.append(pr_data)
                else:
                    print(f"  -> Aviso: Não foi possível obter dados para o PR #{pr_num}.")
        else:
            print(f"-> Modo de análise: PRs mais recentes (limite definido por NUM_PULLS).")
            # Comportamento original: busca os últimos PRs
            pull_requests = github.get_pull_requests(owner, repo_name)
        
        if not pull_requests:
            print(f"-> Nenhum pull request encontrado para {owner}/{repo_name}. Pulando.")
            continue
        
        print(f"-> {len(pull_requests)} pull requests encontrados. Analisando...")
        processed_prs = []
        for pr in pull_requests:
            pr_number = pr['number']
   
            print(f"  -> Analisando PR #{pr_number}...")
            
            # 3. Extrair Diff e Gerar Resumo
            diff_content = github.get_pr_diff(owner, repo_name, pr_number)
            summary = "Resumo não disponível."
            code_smell_analysis = []
            
            total_llm_time_sec = 0.0 

            if diff_content:
                
                llm_analysis_start_time = time.time()  
                
                summary = gemini.get_summary_from_diff(diff_content)
                
                code_smell_analysis = gemini.list_specific_code_smells(diff_content)
                llm_analysis_end_time = time.time()  
                total_llm_time_sec = llm_analysis_end_time - llm_analysis_start_time 
                
                print(f"  -> Tempo de análise do LLM para o PR #{pr_number}: {total_llm_time_sec:.2f} segundos")

# 4. Montar a estrutura simplificada do PR
            pr_data = {
                "pr_number": pr['number'],
                "title": pr['title'],
                "url": pr['html_url'],
                "author": pr['user']['login'],
           
                "summary_gemini": summary.strip(),
                "code_smells": code_smell_analysis,
                "processing_time_sec": total_llm_time_sec 
            }
            processed_prs.append(pr_data)

        # 5. Montar o objeto final para o repositório
        repo_data = {
            "owner": owner,
            "repo": repo_name,
            "programming_language": tech_info["linguagem"],
            "package_file": tech_info["arquivo_dependencias"],
            "vulnerability_report": vulnerability_report,
            "pull_requests": processed_prs
        }
        all_repos_data.append(repo_data)

    # 6. Salvar o resultado final, incluindo os totais de uso da API
    # [MODIFICADO] Gera o timestamp e cria o nome do arquivo dinâmico
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    final_output_path = f"pr_info_final_{timestamp}.json"

    # Obter os totais do cliente Gemini
    total_calls = gemini.get_total_calls()
    total_tokens = gemini.get_total_tokens()
    
    print(f"\n--- Resumo Global da Análise (LLM) ---")
    print(f"Total de Chamadas à API Gemini: {total_calls}")
    print(f"Total de Tokens Gemini Consumidos: {total_tokens}")
    
    # Montar o objeto de saída final com a nova estrutura
    final_data = {
        "run_summary": {
            "total_gemini_api_calls": total_calls,
            "total_gemini_tokens": total_tokens
        },
        "repositories": all_repos_data # A lista de repositórios agora está aninhada
    }
    
    file_handler.save_json(final_data, final_output_path)
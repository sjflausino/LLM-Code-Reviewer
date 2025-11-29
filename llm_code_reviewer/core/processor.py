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
    """Executa o pipeline completo: prioriza commits se existirem, caso contrário processa PRs."""
    github = GitHubClient()
    gemini = GeminiClient()
    osv = OsvClient()
    
    repositorios = file_handler.load_repos(repos_file_path)
    if not repositorios:
        print("Nenhum repositório para analisar. Encerrando.")
        return

    all_repos_data = []

    for repo_info in repositorios:
        owner = repo_info.get('owner')
        repo_name = repo_info.get('repo')
        osv_report = repo_info.get('osv_report', '').lower() == 'true'
        
        # Obtém listas (pode vir vazia)
        pull_requests = repo_info.get('pull_requests', [])
        commits = repo_info.get('commits', [])

        print(f"\n--- Processando Repositório: {owner}/{repo_name} ---")

        processed_prs = []
        processed_commits = []

        if commits:
            print(f"-> Prioridade: Analisando {len(commits)} commits definidos na configuração.")
            
            for commit_item in commits:
                commit_hash = commit_item.get('commit_hash')
                file_name = commit_item.get('file_name') # Pode ser None
                
                print(f"  -> Analisando Commit {commit_hash[:7]}...")
                
                diff_content = ""
                
                # Se tiver nome de arquivo, busca só o patch dele. Se não, busca o diff do commit inteiro.
                if file_name:
                    print(f"    -> Buscando diff apenas para o arquivo: {file_name}")
                    diff_content = github.get_commit_file_patch(owner, repo_name, commit_hash, file_name)
                else:
                    print("    -> Buscando diff completo do commit.")
                    diff_content = github.get_commit_full_diff(owner, repo_name, commit_hash)

                # 2. Análise do Gemini para Commits
                total_llm_time_sec = 0.0
                analysis_result = {"summary": "Sem conteúdo", "code_smells": []}

                if diff_content:
                    llm_analysis_start_time = time.time()
                    
                    analysis_result = gemini.list_commit_code_smells(diff_content)
                    
                    llm_analysis_end_time = time.time()
                    total_llm_time_sec = llm_analysis_end_time - llm_analysis_start_time
                    print(f"    -> Tempo de análise LLM: {total_llm_time_sec:.2f}s")
                else:
                    print("    -> Aviso: Nenhum conteúdo de diff encontrado para analisar.")

                # 3. Montar objeto do Commit
                commit_data = {
                    "commit_hash": commit_hash,
                    "file_analyzed": file_name if file_name else "FULL_COMMIT",
                    "code_smells": analysis_result,
                    "processing_time_sec": total_llm_time_sec
                }
                processed_commits.append(commit_data)

        # SE NÃO TIVER COMMITS, TENTA OS PULL REQUESTS
        else :
            print("-> Nenhum commit específico listado. Buscando Pull Requests...")
            # 1. Coletar Pull Requests
            fetched_prs = github.get_pull_requests(owner, repo_name, pull_requests)
            
            if not fetched_prs:
                print("-> Nenhum pull request encontrado no GitHub. Pulando.")
            else:
                print(f"-> {len(fetched_prs)} pull requests encontrados.")
                
                for pr in fetched_prs:
                    pr_number = pr['number']
                    print(f"  -> Analisando PR #{pr_number}...")
                    
                    diff_content = github.get_pr_diff(owner, repo_name, pr_number)
                    total_llm_time_sec = 0.0 
                    analysis = {"summary": "", "code_smells": []}

                    if diff_content:
                        llm_analysis_start_time = time.time()  
                        analysis = gemini.analyze_pr_diff(diff_content) # Método original de PR
                        llm_analysis_end_time = time.time()  
                        total_llm_time_sec = llm_analysis_end_time - llm_analysis_start_time 
                        print(f"    -> Tempo de análise do LLM: {total_llm_time_sec:.2f}s")

                    pr_data = {
                        "pr_number": pr['number'],
                        "title": pr['title'],
                        "url": pr['html_url'],
                        "author": pr['user']['login'],
                        "summary_gemini": analysis.get("summary"),
                        "code_smells": analysis.get("code_smells"),
                        "processing_time_sec": total_llm_time_sec 
                    }
                    processed_prs.append(pr_data)


        tech_info = {"linguagem": "desconhecido", "arquivo_dependencias": "desconhecido"}
        vulnerability_report = []
        if osv_report:

            print("-> Iniciando análise de vulnerabilidades...")
            # 1. Analisar Tecnologia do Repositório
            file_paths = github.get_repo_structure(owner, repo_name)
            if file_paths:
                tech_info = gemini.infer_tech_from_files(file_paths)
                print(f"-> Tecnologia inferida: {tech_info['linguagem']}")
            
            # --- Bloco de Análise de Vulnerabilidades ---
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

        # 4. Montar o objeto final para o repositório
        repo_data = {
            "owner": owner,
            "repo": repo_name,
            "programming_language": tech_info["linguagem"],
            "package_file": tech_info["arquivo_dependencias"],
            "vulnerability_report": vulnerability_report
        }

        # Adiciona o campo relevante baseado no que foi processado
        if processed_commits:
            repo_data["commits_analysis"] = processed_commits
        elif processed_prs:
            repo_data["pull_requests"] = processed_prs

        if not osv_report:
            repo_data.pop("programming_language", None)
            repo_data.pop("package_file", None)
            repo_data.pop("vulnerability_report", None)

        all_repos_data.append(repo_data)

    # 5. Salvar o resultado final
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    final_output_path = f"pr_info_final_{timestamp}.json"

    total_calls = gemini.get_total_calls()
    total_tokens = gemini.get_total_tokens()
    
    print("\n--- Resumo Global da Análise (LLM) ---")
    print(f"Total de Chamadas à API Gemini: {total_calls}")
    print(f"Total de Tokens Gemini Consumidos: {total_tokens}")
    
    final_data = {
        "run_summary": {
            "total_gemini_api_calls": total_calls,
            "total_gemini_tokens": total_tokens
        },
        "repositories": all_repos_data
    }
    
    file_handler.save_json(final_data, final_output_path)
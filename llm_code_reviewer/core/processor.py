import time  # <-- NOVO: Importa a biblioteca de tempo

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
        print(f"\n--- Processando Repositório: {owner}/{repo_name} ---")

        # 1. Analisar Tecnologia do Repositório
        file_paths = github.get_repo_structure(owner, repo_name)
        tech_info = {"linguagem": "desconhecido", "arquivo_dependencias": "desconhecido"}
        if file_paths:
            # (Vamos assumir que esta chamada ao Gemini é rápida e focar o tempo no PR)
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
                    # (Esta é uma chamada de API, mas não é do LLM - RQ2 foca no LLM)
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
            
            total_llm_time_sec = 0.0  # <-- NOVO: Inicializa o contador de tempo

            if diff_content:
                
                llm_analysis_start_time = time.time()  # <-- NOVO: Inicia o timer
                
                summary = gemini.get_summary_from_diff(diff_content)
                
                # --- LÓGICA DE ANÁLISE DE CODE SMELL ---
                # 1. Primeira verificação: existe algum code smell?
                smell_detection_result = gemini.detect_code_smell(diff_content)
                
                # 2. Se a primeira verificação for positiva, busca os detalhes
                if smell_detection_result.get("has_code_smell"):
                    print(f"  -> Code smells detectados no PR #{pr_number}. Justificativa: {smell_detection_result.get('justification')}")
                    # Chama a segunda função para obter a lista detalhada
                    code_smell_analysis = gemini.list_specific_code_smells(diff_content)
                else:
                    print(f"   -> Nenhuma detecção de code smell no PR #{pr_number}.")

                llm_analysis_end_time = time.time()  # <-- NOVO: Para o timer
                total_llm_time_sec = llm_analysis_end_time - llm_analysis_start_time # <-- NOVO: Calcula a duração
                
                print(f"  -> Tempo de análise do LLM para o PR #{pr_number}: {total_llm_time_sec:.2f} segundos")

            # 4. Montar a estrutura simplificada do PR, agora incluindo a análise
            pr_data = {
                "pr_number": pr['number'],
                "title": pr['title'],
                "url": pr['html_url'],
                "author": pr['user']['login'],
                "summary_gemini": summary.strip(),
                "code_smells": code_smell_analysis,
                "processing_time_sec": total_llm_time_sec  # <-- NOVO: Adiciona o tempo ao dict
            }
            processed_prs.append(pr_data)

        # 5. Montar o objeto final para o repositório
        repo_data = {
            "owner": owner,
            "repo": repo_name,
            "programming_language": tech_info["linguagem"],
            "package_file": tech_info["arquivo_dependencias"],
            "vulnerability_report": vulnerability_report, # Adiciona o relatório
            "pull_requests": processed_prs
        }
        all_repos_data.append(repo_data)

    # 6. Salvar o resultado final
    final_output_path = "pr_info_final.json"
    file_handler.save_json(all_repos_data, final_output_path)
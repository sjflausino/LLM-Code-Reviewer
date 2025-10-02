import json
import os
import google.generativeai as genai

# Configura a chave da API do Google a partir da variável de ambiente
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_gemini_summary(diff_content):
    """
    Chama a API do Gemini para gerar um resumo de um diff.
    """
    if not GEMINI_API_KEY:
        print("Erro: A variável de ambiente GEMINI_API_KEY não está definida.")
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        prompt = (
            "Você é um assistente de IA focado em análise de código. Sua tarefa é fornecer um resumo claro e conciso das alterações em um Pull Request com base no seguinte diff (código e metadados). O resumo deve focar em:\n"
            "1. **O que foi mudado**: Resumo das principais alterações de código (adição, remoção, modificação).\n"
            "2. **Por que foi mudado**: Explicação concisa da intenção por trás da mudança, se o diff fornecer contexto suficiente.\n\n"
            "A resposta deve ser um parágrafo único.\n\n"
            "```diff\n"
            f"{diff_content}"
            "```"
        )
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Erro ao chamar a API do Gemini: {e}")
        return None

def main():
    # Define os nomes de arquivos de entrada e saída
    input_file = "pr_info_simplificado.json"
    output_file = "pr_info_simplificado_com_resumo.json"

    if not os.path.exists(input_file):
        print(f"Erro: O arquivo '{input_file}' não foi encontrado. Execute o job anterior primeiro.")
        return

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            repos_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Erro ao ler {input_file}: {e}")
        return

    print("Iniciando a geração de resumos com a API do Gemini...")

    # Itera sobre cada repositório e seus pull requests
    for repo_info in repos_data:
        owner = repo_info.get('owner')
        repo_name = repo_info.get('repo')
        
        for pr_data in repo_info.get('pull_requests', []):
            pr_number = pr_data['referencia'].split('#')[-1]
            diff_file_path = f"diffs/{owner}/{repo_name}/pr_{pr_number}.diff"
            
            pr_summary = "Resumo não disponível."
            
            if os.path.exists(diff_file_path):
                print(f"-> Gerando resumo para {owner}/{repo_name}#{pr_number}...")
                with open(diff_file_path, 'r', encoding='utf-8') as f:
                    diff_content = f.read()
                
                pr_summary = get_gemini_summary(diff_content)
                
            else:
                print(f"Aviso: Arquivo de diff não encontrado para {owner}/{repo_name}#{pr_number}. Pulando resumo.")
            
            # Adiciona o resumo ao dicionário do PR
            pr_data["resumo_gemini"] = pr_summary or "Resumo não disponível."

    # Salva o JSON atualizado
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(repos_data, f, indent=2, ensure_ascii=False)
        
    print(f"Dados com resumos do Gemini salvos em '{output_file}'.")

if __name__ == "__main__":
    main()
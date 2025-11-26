# LLM-Code-Reviewer

Este é um projeto Python que utiliza as APIs do Google Gemini e do GitHub para coletar, analisar e resumir Pull Requests de múltiplos repositórios.

O objetivo é automatizar a análise de código, fornecendo resumos concisos , detectando "code smells" (padrões de código problemáticos) e inferindo as tecnologias usadas no projeto, facilitando o trabalho de revisores humanos.

## 🚀 Como Funciona

O pipeline de análise principal (`run_analysis_pipeline`) é orquestrado pelo `main.py` e executa as seguintes etapas para cada repositório configurado:

1.  **Carrega Repositórios**: Lê a lista de repositórios de um arquivo JSON (ex: `repositorios.json`).
2.  **Analisa Estrutura**: Busca a estrutura de arquivos do repositório (árvore de arquivos).
3.  **Infere Tecnologia**: Usa a API do Gemini para analisar a lista de arquivos e inferir a linguagem de programação principal e o arquivo de gerenciamento de dependências.
4.  **Coleta Pull Requests**: Busca os Pull Requests mais recentes do repositório.
5.  **Gera Análise por PR**: Para cada Pull Request individual:
      * Extrai o conteúdo do "diff" (as alterações de código).
      * Usa o Gemini para gerar um resumo focado no "o que foi mudado" e "por que foi mudado".
      * Usa o Gemini para uma detecção inicial, determinando se o diff *contém* algum code smell.
      * Se um code smell for detectado , uma segunda chamada ao Gemini é feita para listar e descrever cada problema específico , incluindo uma sugestão de refatoração.
6.  **Salva Resultado**: Agrega todos os dados (informações do repositório, tecnologia inferida, PRs, resumos e análises de code smells ) e salva em um único arquivo `pr_info_final.json`.

## 🛠️ Requisitos e Configuração

Para executar este projeto localmente, você precisará de:

1.  **Python** (O ambiente do GitHub Actions usa a versão 3.10 ).

2.  **Dependências Python**: Instale as dependências listadas no `requirements.txt`:

    ```bash
    pip install -r requirements.txt
    ```

3.  **Arquivo de Repositórios**: Crie um arquivo `repositorios.json` (ou o nome definido em `.env` ) na raiz do projeto com a lista de repositórios que deseja analisar.

    O formato deve ser:

    ```json
    [
      {
        "owner": "dono_do_repo", // obrigatório
        "repo": "nome_do_repo", // obrigatório
        "url": "https://github.com/path_do_repositorio", // obrigatório
        "pull_requests": [1, 2, 3], // opcional, default = []
        "osv_report": "true" // opcional, default = false
      }
    ]
    ```

4.  **Variáveis de Ambiente**: Crie um arquivo `.env` na raiz do projeto (baseado no `config.py` e no arquivo `.env` de exemplo).

    ```ini
    # [cite_start]Token de Acesso Pessoal do GitHub com escopo 'repo' 
    GITHUB_TOKEN="ghp_seu_token_aqui"

    # [cite_start]Chave de API do Google Gemini 
    GEMINI_API_KEY="AIzaSy_sua_chave_aqui"

    # [cite_start]Opcional: Número de PRs para buscar por repositório 
    NUM_PULLS="5" 

    # [cite_start]Opcional: Caminho para o arquivo de repositórios 
    REPOS_FILE="repositorios.json"
    ```

## 🏃 Como Usar

Após concluir a configuração (instalar dependências, criar `repositorios.json` e `.env`), basta executar o script principal:

```bash
python main.py
```

O script exibirá o progresso da análise no console e, ao final, salvará o resultado completo no arquivo `pr_info_final.json` (este arquivo é ignorado pelo `.gitignore`).

## 📁 Estrutura do Projeto

```
llm_code_reviewer/
├── api/
│   ├── github_client.py   # Cliente para interagir com a API do GitHub 
│   └── gemini_client.py   # Cliente para interagir com a API do Gemini 
├── core/
│   ├── processor.py       # Contém a lógica principal do pipeline de análise 
│   └── file_handler.py    # Funções para ler e salvar arquivos (JSON, diffs) 
├── config.py              # Carrega e valida as variáveis de ambiente 
└── ...
main.py                    # Ponto de entrada da aplicação 
requirements.txt           # Dependências do Python 
.env                       # Arquivo local para chaves de API (ignorado) 
repositorios.json          # Lista de repositórios a analisar
```

## 🤝 Contribuições

Sinta-se à vontade para contribuir\! Seja corrigindo um bug, melhorando a documentação, ou adicionando novas funcionalidades. 
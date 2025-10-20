# LLM-Code-Reviewer

Este é um projeto Python que utiliza as APIs do Google Gemini [cite: 13, 34] e do GitHub [cite: 12, 54] para coletar, analisar e resumir Pull Requests de múltiplos repositórios.

O objetivo é automatizar a análise de código, fornecendo resumos concisos [cite: 3], detectando "code smells" (padrões de código problemáticos) [cite: 45, 71] e inferindo as tecnologias usadas no projeto[cite: 40, 67], facilitando o trabalho de revisores humanos.

## 🚀 Como Funciona

O pipeline de análise principal (`run_analysis_pipeline` [cite: 66]) é orquestrado pelo `main.py` e executa as seguintes etapas para cada repositório configurado:

1.  **Carrega Repositórios**: Lê a lista de repositórios de um arquivo JSON (ex: `repositorios.json`)[cite: 14, 66].
2.  **Analisa Estrutura**: Busca a estrutura de arquivos do repositório (árvore de arquivos)[cite: 58, 67].
3.  **Infere Tecnologia**: Usa a API do Gemini para analisar a lista de arquivos e inferir a linguagem de programação principal e o arquivo de gerenciamento de dependências[cite: 40, 41, 42, 67].
4.  **Coleta Pull Requests**: Busca os Pull Requests mais recentes do repositório[cite: 55, 68].
5.  **Gera Análise por PR**: Para cada Pull Request individual:
      * Extrai o conteúdo do "diff" (as alterações de código)[cite: 57, 70].
      * Usa o Gemini para gerar um resumo focado no "o que foi mudado" e "por que foi mudado"[cite: 35, 37, 38].
      * Usa o Gemini para uma detecção inicial, determinando se o diff *contém* algum code smell[cite: 45, 47, 71].
      * Se um code smell for detectado [cite: 73], uma segunda chamada ao Gemini é feita para listar e descrever cada problema específico [cite: 50, 73], incluindo uma sugestão de refatoração[cite: 51].
6.  **Salva Resultado**: Agrega todos os dados (informações do repositório, tecnologia inferida, PRs, resumos e análises de code smells [cite: 75, 76, 77]) e salva em um único arquivo `pr_info_final.json`[cite: 66].

## 🛠️ Requisitos e Configuração

Para executar este projeto localmente, você precisará de:

1.  **Python** (O ambiente do GitHub Actions usa a versão 3.10 [cite: 23, 29]).

2.  **Dependências Python**: Instale as dependências listadas no `requirements.txt`[cite: 22]:

    ```bash
    pip install -r requirements.txt
    ```

3.  **Arquivo de Repositórios**: Crie um arquivo `repositorios.json` (ou o nome definido em `.env` [cite: 2]) na raiz do projeto com a lista de repositórios que deseja analisar[cite: 14].

    O formato deve ser[cite: 15]:

    ```json
    [
      {
        "owner": "dono_do_repo",
        "repo": "nome_do_repo"
      }
    ]
    ```

4.  **Variáveis de Ambiente**: Crie um arquivo `.env` na raiz do projeto [cite: 2] (baseado no `config.py` [cite: 63] e no arquivo `.env` de exemplo [cite: 2]).

    ```ini
    # [cite_start]Token de Acesso Pessoal do GitHub com escopo 'repo' [cite: 12]
    GITHUB_TOKEN="ghp_seu_token_aqui"

    # [cite_start]Chave de API do Google Gemini [cite: 13]
    GEMINI_API_KEY="AIzaSy_sua_chave_aqui"

    # [cite_start]Opcional: Número de PRs para buscar por repositório [cite: 2, 55]
    NUM_PULLS="5" 

    # [cite_start]Opcional: Caminho para o arquivo de repositórios [cite: 2]
    REPOS_FILE="repositorios.json"
    ```

## 🏃 Como Usar

Após concluir a configuração (instalar dependências, criar `repositorios.json` e `.env`), basta executar o script principal:

```bash
python main.py
```

O script exibirá o progresso da análise no console [cite: 67, 69, 73, 74] e, ao final, salvará o resultado completo no arquivo `pr_info_final.json` [cite: 66] (este arquivo é ignorado pelo `.gitignore` [cite: 2]).

## 📁 Estrutura do Projeto

```
llm_code_reviewer/
├── api/
[cite_start]│   ├── github_client.py   # Cliente para interagir com a API do GitHub [cite: 54]
[cite_start]│   └── gemini_client.py   # Cliente para interagir com a API do Gemini [cite: 34]
├── core/
[cite_start]│   ├── processor.py       # Contém a lógica principal do pipeline de análise [cite: 66]
[cite_start]│   └── file_handler.py    # Funções para ler e salvar arquivos (JSON, diffs) [cite: 64, 65]
[cite_start]├── config.py              # Carrega e valida as variáveis de ambiente [cite: 63]
└── ...
[cite_start]main.py                    # Ponto de entrada da aplicação [cite: 66]
[cite_start]requirements.txt           # Dependências do Python [cite: 22]
[cite_start].env                       # Arquivo local para chaves de API (ignorado) [cite: 2]
repositorios.json          # Lista de repositórios a analisar
```

## 🤝 Contribuições

Sinta-se à vontade para contribuir\! Seja corrigindo um bug, melhorando a documentação, ou adicionando novas funcionalidades. [cite: 21]
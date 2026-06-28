# ⚖️ Juri-AI

> Um sistema inteligente e eficiente para gestão de clientes e documentos jurídicos, com foco em automação e IA.

![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)
![Django](https://img.shields.io/badge/Django-5+-green?style=for-the-badge&logo=django)
![Status](https://img.shields.io/badge/Status-Em_Desenvolvimento-yellow?style=for-the-badge)

---

## 📋 Sobre o Projeto

O **Juri-AI** é uma plataforma web inteligente criada para modernizar a rotina de advogados e escritórios de advocacia.
Ela centraliza o gerenciamento de clientes e documentos jurídicos, garantindo acesso rápido, seguro e personalizado para cada profissional.

Além da gestão tradicional, o projeto integra tecnologias de Inteligência Artificial para automatizar tarefas repetitivas e análises documentais, como:

- Leitura e interpretação de documentos jurídicos (OCR).
- Conversão de arquivos para formatos padronizados (Markdown).
- Busca inteligente em documentos usando técnicas de RAG (Retrieval-Augmented Generation).
- Processamento assíncrono de tarefas pesadas, garantindo eficiência sem travar o sistema.

O Juri-AI une segurança, automação e inteligência, transformando dados jurídicos complexos em informações acessíveis e organizadas, permitindo que advogados foquem no que realmente importa: analisar casos e tomar decisões estratégicas.

---

## ✨ Funcionalidades Principais

### 🔐 Autenticação Segura
- Cadastro de usuários com validação de senha.
- Login e logout utilizando Django Auth.
- Proteção de rotas (apenas usuários autenticados).

### 👥 Gestão de Clientes
- Cadastro detalhado de clientes (Nome, E-mail, Tipo, Status).
- Listagem de clientes exclusiva por usuário (multi-tenancy).
- Visualização de dados individuais de cada cliente.

### 📂 Gestão Documental
- Upload de documentos vinculados a clientes.
- Organização por tipo de documento.
- Histórico de uploads com data e responsável.

### 🗂️ Painel de Gestão Jurídica (app `gestao`)
- **Dashboard / Indicadores:** visão geral com processos ativos, prazos a vencer, audiências próximas, tarefas abertas e resumo financeiro.
- **Processos judiciais:** cadastro completo (número CNJ, área, vara, comarca, instância, valor da causa), filtros, busca e registro de movimentações/andamentos.
- **Agenda:** linha do tempo unificada de compromissos e audiências.
- **Audiências:** agendamento e acompanhamento por status (agendada, realizada, cancelada, adiada).
- **Prazos:** controle de prazos processuais com prioridade, alerta de vencimento/atraso e marcação de cumprimento.
- **Tarefas:** quadro de rotina (a fazer / em andamento / concluídas).
- **Financeiro:** receitas, despesas, honorários, saldo, a receber e a pagar.
- **Relatórios:** processos por área e status, prazos cumpridos/perdidos e receitas por categoria.
- **Controle de acessos:** perfis de usuário por cargo (Administrador, Advogado, Estagiário, Secretária, Financeiro).

---

## 🤖 Assistente de IA (app `ia`)

Pipeline de IA que processa cada documento enviado e permite consultá-los em linguagem natural:

- 🔍 **OCR / Conversão para Markdown** via `docling` (com fallback de leitura simples).
- 🔗 **RAG (Retrieval-Augmented Generation)** — o conteúdo é dividido em trechos, vetorizado por *embeddings* e indexado no `LanceDB`.
- 💬 **Assistente Jurídico** (`/ia/assistente/`) — faça perguntas sobre os documentos; as respostas são geradas pelo **Claude (Anthropic)** com os trechos-fonte citados.
- ⏱️ **Processamento assíncrono** com `django-q` (OCR → indexação encadeados no upload).

> **Configuração da IA:**
> - **Respostas (Claude):** defina `ANTHROPIC_API_KEY` (opcional: `IA_CLAUDE_MODEL`, padrão `claude-opus-4-8`). É a **única chave obrigatória**.
> - **Embeddings (busca):** a Anthropic não oferece embeddings, então o backend é configurável via `IA_EMBEDDING_BACKEND`:
>   - `local` *(padrão)* — roda via `transformers`, **sem chave de API** (`IA_EMBEDDING_MODEL_LOCAL`, padrão `all-MiniLM-L6-v2`).
>   - `openai` — requer `OPENAI_API_KEY` (`IA_EMBEDDING_MODEL`).
>   - `voyage` — requer `VOYAGE_API_KEY` (`IA_VOYAGE_MODEL`), parceira recomendada pela Anthropic.
>
> ⚠️ Ao trocar de backend de embeddings, reindexe os documentos (apague a pasta `lancedb/`), pois as dimensões dos vetores mudam.
>
> Sem as chaves/dependências o sistema continua funcionando e o assistente exibe um aviso de configuração.

---

## 🚀 Tecnologias Utilizadas

- **Backend:** Python, Django Framework  
- **Frontend:** HTML, CSS (Django Templates)  
- **Banco de Dados:** SQLite (Desenvolvimento) / PostgreSQL (Produção)
- **IA & Processamento:** OCR, Markdown, RAG  
- **Tarefas Assíncronas:** Django-Q / Celery

---

## 💻 Pré-requisitos

Antes de iniciar, certifique-se de ter instalado:

- Python 3.12+
- Pip (gerenciador de pacotes)
- Git

---

## 🔧 Instalação e Execução

Siga os passos abaixo para rodar o projeto localmente:

### 1️⃣ Clone o repositório
```bash
git clone https://github.com/GuilhermeBeserra/JURI-AI.git
cd Juri-AI
```

### 2️⃣ Crie o ambiente virtual
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / Mac
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Instale as dependências
```bash
pip install -r requirements.txt
```

### 4️⃣ Configure o Banco de Dados
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5️⃣ Inicie o servidor
```bash
python manage.py runserver
```

Acesse o projeto em: `http://127.0.0.1:8000/`

### 6️⃣ Rodar os testes
```bash
python manage.py test
```
A suíte cobre perfis/controle de acesso, multi-tenancy, fluxos de processos/prazos/tarefas/financeiro e a camada de IA (chunking, seleção de backend e degradação graciosa).

---

## ⚙️ Configuração e Boas Práticas

### 🛡️ .gitignore e Banco de Dados
Para manter o repositório limpo e seguro, certifique-se de que seu arquivo `.gitignore` inclua os seguintes itens:

```text
venv/
*.pyc
__pycache__/
db.sqlite3
.env
```

> **⚠️ Aviso Importante:** O arquivo `db.sqlite3` **não deve ser versionado**. Cada ambiente (desenvolvimento, produção) deve possuir seu próprio banco de dados, criado e atualizado através das migrações do Django.

---

## Estrutura do Projeto

```text
Juri-AI/
├── core/                # Configurações principais do projeto (settings, urls)
├── gestao/              # Painel de gestão: processos, agenda, prazos, audiências,
│                        #   tarefas, financeiro, relatórios e controle de acessos
├── ia/                  # Contém tasks e lógica de IA
├── templates/           # Contém static/ e templates globais (base + sidebar)
├── usuarios/            # Autenticação, clientes e documentos
├── manage.py            # Utilitário de linha de comando
├── requirements.txt     # Dependências do projeto
└── README.md            # Documentação
```

---

## 📚 Documentação Útil

- [Django Docs](https://docs.djangoproject.com/)
- [Python](https://www.python.org/)
- [Django-Q Docs](https://django-q.readthedocs.io/en/latest/) / [Celery Docs](https://docs.celeryq.dev/en/stable/)

---

## ⚠️ Aviso Legal

Este projeto não substitui a atuação de um advogado.
As informações geradas pelo sistema e pela IA servem apenas como apoio à análise jurídica.

---

## 📝 Licença

Este projeto está licenciado sob a **Apache License 2.0**.  
Versões anteriores do projeto utilizaram a **MIT License**.

**Sinta-se à vontade para estudar, modificar e evoluir o código.**


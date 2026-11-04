# Desvios Onisys

Script em Python que busca os desvios na API da Onisys e grava na tabela `desvios` do Supabase. Pode ser rodado de tempos em tempos (por exemplo, a cada 5 minutos com o `cron`), mantendo a base sempre atualizada.

## O que o script faz

1. Divide os últimos 7 dias em janelas de 24 horas.
2. Para cada janela e para cada status (`ABERTO`, `PENDENTE`, `FINALIZADO`, `DELETADO`), consulta a API da Onisys. As consultas rodam em paralelo.
3. Extrai o código da viagem (`cd_viagem`) e descarta a linha inteira quando ele estiver vazio, for só número ou tiver menos de 10 caracteres.
4. Monta os registros, trocando valores inválidos (`NaN`, infinito, texto vazio e `"nan"`) por nulo.
5. Envia os registros ao Supabase em lotes de 500. Se o `id` já existir na tabela, a linha é atualizada; se não existir, é inserida.

## Requisitos

- Python 3.10 ou superior
- Uma tabela `desvios` no Supabase, com a coluna `id` como chave primária (necessário para a atualização funcionar)

## Instalação

```bash
git clone https://github.com/nothdz/desvios_onisys.git
cd desvios_onisys

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

No Ubuntu, se o ambiente virtual não for criado, instale antes o módulo: `sudo apt install python3-venv`.

## Configuração

Crie um arquivo `.env` na mesma pasta do script:

```
ONISYS_USUARIO=seu_usuario
ONISYS_TOKEN=seu_token
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua_chave
```

> O `.env` contém chaves de acesso e **nunca** deve ser enviado ao GitHub. Ele já está no `.gitignore`.

## Uso

Execução manual:

```bash
python desvios_onisys.py
```

### Agendamento a cada 5 minutos (cron)

Abra o agendador:

```bash
crontab -e
```

Adicione a linha, trocando o caminho pelo da sua pasta:

```
*/5 * * * * cd /caminho/desvios_onisys && flock -n /tmp/desvios.lock ./venv/bin/python desvios_onisys.py >> log.txt 2>&1
```

- `flock -n` evita que duas execuções rodem ao mesmo tempo.
- A saída do script (inclusive erros) fica no `log.txt`.

Para conferir o resultado das últimas execuções:

```bash
tail -n 20 log.txt
```

## Configurações do script

| Item | Onde alterar | Padrão |
|---|---|---|
| Dias de busca | `dias_busca` | 7 |
| Status consultados | `lista_status` | ABERTO, PENDENTE, FINALIZADO, DELETADO |
| Tamanho máximo do `cd_viagem` | `filtro_valido` | 10 caracteres |
| Registros por lote | `chunk_size` | 500 |
| Consultas simultâneas | `max_workers` | 10 |

## Pontos de atenção

- Só os desvios que ainda aparecem na janela de busca são atualizados. Mudanças de status feitas depois que o desvio saiu da janela não chegam à base.
- Todos os campos enviados são sobrescritos, inclusive com nulo.
- O filtro do `cd_viagem` impede a entrada de novas linhas curtas, mas não apaga as que já estão na tabela.
- O `log.txt` cresce com o tempo. Limpe de vez em quando com `> log.txt`.

## Estrutura

```
desvios_onisys/
├── desvios_onisys.py   # script principal
├── requirements.txt    # dependências
├── .env                # chaves de acesso (não vai para o GitHub)
└── .gitignore
```

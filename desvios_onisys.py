from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd
import requests
import truststore

# Injeta os certificados nativos do SO no requests
truststore.inject_into_ssl()

load_dotenv()

ONISYS_USUARIO = os.getenv("ONISYS_USUARIO")
ONISYS_TOKEN = os.getenv("ONISYS_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not ONISYS_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
  print("Erro: Verifique se as variáveis de ambiente estão configuradas no .env")
  exit(1)

lista_status = ["ABERTO", "PENDENTE", "FINALIZADO", "DELETADO"]
dias_busca = 7

hoje = datetime.now()
data_limite_inicio = hoje - timedelta(days=dias_busca)

intervalos = []
cursor_inicio = data_limite_inicio
while cursor_inicio < hoje:
  cursor_fim = cursor_inicio + timedelta(hours=24)
  if cursor_fim > hoje:
    cursor_fim = hoje

  intervalos.append({
      "inicio": cursor_inicio.strftime("%Y-%m-%d %H:%M:%S"),
      "fim": cursor_fim.strftime("%Y-%m-%d %H:%M:%S"),
  })
  cursor_inicio = cursor_fim

requisicoes = []
for intervalo in intervalos:
  for status in lista_status:
    url = (
        f"https://api-clientes.onisys.com.br/desvios?usuario={ONISYS_USUARIO}"
        f"&token={ONISYS_TOKEN}&status={status}"
        f"&data_hora_inicio={intervalo['inicio']}&data_hora_fim={intervalo['fim']}"
    )
    requisicoes.append(url)


def buscar_api(url):
  try:
    resp = requests.get(url, timeout=30)
    if resp.status_code == 200:
      dados = resp.json()
      if not isinstance(dados, list):
        dados = (
            dados.get("dados")
            or dados.get("data")
            or dados.get("desvios")
            or dados.get("items")
            or []
        )
      return dados if isinstance(dados, list) else []
  except Exception as e:
    print(f"Erro na requisição: {e}")
  return []


todos_desvios = []
print(f"Buscando {len(requisicoes)} janelas/status em paralelo...")
with ThreadPoolExecutor(max_workers=10) as executor:
  futures = {executor.submit(buscar_api, url): url for url in requisicoes}
  for future in as_completed(futures):
    resultado = future.result()
    if resultado:
      todos_desvios.extend(resultado)

if not todos_desvios:
  print("Nenhum dado retornado da Onisys.")
  exit(0)

df = pd.DataFrame(todos_desvios)


def extrair_viagem(row):
  viagem = row.get("cd_viagem")
  if pd.isna(viagem):
    viagem = row.get("viagem")

  if isinstance(viagem, dict):
    viagem = viagem.get("codigo") or viagem.get("cd_viagem") or viagem.get("id")

  return str(viagem).strip() if viagem is not None else ""


df["viagem_tratada"] = df.apply(extrair_viagem, axis=1)


def filtro_valido(val):
  if not val:
    return False
  return not val.isdigit()


df_filtrado = df[df["viagem_tratada"].apply(filtro_valido)].copy()

if df_filtrado.empty:
  print("Nenhum registro passou no filtro de viagem.")
  exit(0)


def limpar_nulo(val):
  """Troca NaN, infinito, texto vazio e "nan" por None (vira null no JSON)."""
  if val is None:
    return None
  if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
    return None
  if isinstance(val, str) and (not val.strip() or val.lower() == "nan"):
    return None
  return val


registros = []
for _, row in df_filtrado.iterrows():
  motorista = row.get("motorista")
  nome_motorista = (
      motorista.get("nome") if isinstance(motorista, dict) else ""
  )

  veiculo = row.get("veiculo")
  placa_veiculo = veiculo.get("placa") if isinstance(veiculo, dict) else ""

  registros.append({
      "id": str(row.get("id")),
      "cd_viagem": limpar_nulo(row.get("viagem_tratada")),
      "motorista": limpar_nulo(nome_motorista),
      "veiculo": limpar_nulo(placa_veiculo),
      "data_desvio": limpar_nulo(row.get("data_desvio")),
      "tipo": limpar_nulo(row.get("tipo")),
      "criticidade": limpar_nulo(row.get("criticidade")),
      "status": limpar_nulo(row.get("status")),
      "velocidade_limite": limpar_nulo(row.get("velocidade_limite")),
      "latitude": limpar_nulo(row.get("latitude")),
      "longitude": limpar_nulo(row.get("longitude")),
      "valor": limpar_nulo(row.get("valor")),
  })

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}

url_supabase = f"{SUPABASE_URL}/rest/v1/desvios"

chunk_size = 500
for i in range(0, len(registros), chunk_size):
  lote = registros[i : i + chunk_size]
  resp = requests.post(url_supabase, headers=headers, json=lote)
  if resp.status_code not in (200, 201, 204):
    print(f"Erro ao enviar para o Supabase: {resp.status_code} - {resp.text}")
  else:
    print(f"Lote {i} enviado com sucesso.")

print(f"Sincronização concluída. Total processado: {len(registros)} registros.")
"""Cliente mínimo da SerpApi (Google Trends + Account API).

A chave nunca é impressa nem gravada: mensagens de erro passam por _sem_chave().
"""
from __future__ import annotations

import time
from typing import Any

import requests

URL_BUSCA = "https://serpapi.com/search.json"
URL_CONTA = "https://serpapi.com/account.json"


class ErroSerpApi(Exception):
    """Erro genérico da API."""


class ErroAutenticacao(ErroSerpApi):
    """Chave inválida ou ausente (HTTP 401)."""


class ErroCota(ErroSerpApi):
    """Cota mensal ou limite por hora estourado."""


class SemResultados(ErroSerpApi):
    """O Google Trends não devolveu dados para a busca (volume baixo)."""


class ClienteSerpApi:
    def __init__(self, api_key: str, timeout: int = 60, tentativas: int = 3):
        if not api_key:
            raise ErroAutenticacao("SERPAPI_KEY não definida (veja .env.example).")
        self._key = api_key
        self.timeout = timeout
        self.tentativas = tentativas
        self.sessao = requests.Session()

    # ------------------------------------------------------------------ util
    def _sem_chave(self, texto: str) -> str:
        return str(texto).replace(self._key, "***")

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "api_key": self._key}
        espera = 5
        for tentativa in range(1, self.tentativas + 1):
            try:
                r = self.sessao.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                if tentativa == self.tentativas:
                    raise ErroSerpApi(self._sem_chave(f"Falha de rede: {e}")) from None
                time.sleep(espera)
                espera *= 2
                continue

            if r.status_code == 401:
                raise ErroAutenticacao("Chave SerpApi inválida (HTTP 401).")
            if r.status_code == 429:
                raise ErroCota("Limite da SerpApi atingido (HTTP 429).")
            if r.status_code >= 500 and tentativa < self.tentativas:
                time.sleep(espera)
                espera *= 2
                continue

            try:
                dados = r.json()
            except ValueError:
                raise ErroSerpApi(f"Resposta não-JSON (HTTP {r.status_code}).") from None

            erro = dados.get("error")
            if erro:
                msg = self._sem_chave(erro)
                baixo = msg.lower()
                if "run out of searches" in baixo or "hourly" in baixo:
                    raise ErroCota(msg)
                if "hasn't returned any results" in baixo or "no results" in baixo:
                    raise SemResultados(msg)
                raise ErroSerpApi(msg)
            if r.status_code >= 400:
                raise ErroSerpApi(f"HTTP {r.status_code}")
            return dados
        raise ErroSerpApi("Esgotadas as tentativas.")

    # ------------------------------------------------------------------ API
    def conta(self) -> dict[str, Any]:
        """Account API: gratuita, não consome buscas."""
        dados = self._get(URL_CONTA, {})
        dados.pop("api_key", None)
        return dados

    def trends(self, params: dict[str, Any]) -> dict[str, Any]:
        """Uma chamada ao Google Trends = 1 busca da cota (se não vier do cache)."""
        return self._get(URL_BUSCA, {"engine": "google_trends", **params})

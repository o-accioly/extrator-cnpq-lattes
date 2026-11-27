"""Filtros da busca do CNPq: o mesmo formulário de buscatextual.cnpq.br.

``FiltrosBusca`` guarda o que o usuário escolheu na interface. ``para_formulario()``
traduz para os nomes de campo do formulário real; o navegador preenche esses campos
na página do CNPq e clica em "Buscar" (o próprio site monta a consulta e roda o
reCAPTCHA invisível dele).
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field, fields
from functools import lru_cache
from pathlib import Path


def _pasta_dados() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "lattes_extrator" / "data"
    return p if p.exists() else Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def catalogo() -> dict:
    try:
        return json.loads((_pasta_dados() / "catalogo_filtros.json").read_text(encoding="utf-8"))
    except OSError:
        return {}


def opcoes(chave: str) -> list[dict]:
    return catalogo().get(chave, [])


def rotulo(chave: str, valor: str) -> str:
    for o in opcoes(chave):
        if o["valor"] == valor:
            return o["texto"]
    return valor


def buscar_area(codigo: str) -> list[dict]:
    """Caminho na árvore de áreas até ``codigo`` (lista de nós)."""
    def rec(nos, caminho):
        for n in nos:
            if n["valor"] == codigo:
                return caminho + [n]
            r = rec(n.get("filhos", []), caminho + [n])
            if r:
                return r
        return None
    return rec(catalogo().get("areasAtuacao", []), []) or []


@dataclass
class FiltrosBusca:
    # Busca simples
    modo: str = "nome"                 # "nome" ou "assunto"
    texto: str = ""
    doutores: bool = True
    demais: bool = False
    brasileiros: bool = True
    estrangeiros: bool = True
    pais_nascimento: str = "0"
    atualizacao_meses: int = 48

    # Filtros (as 10 caixas da página do CNPq)
    bolsa_categorias: list[str] = field(default_factory=list)        # 1A..2, A, B, C
    bolsa_modalidade: str = "0"
    formacao_nivel: str = "0"
    formacao_pais: str = "0"
    formacao_regiao: str = "0"
    formacao_uf: str = "0"
    formacao_instituicao: str = ""
    conceito_curso: list[str] = field(default_factory=list)          # 1..7
    atuacao_grande_area: str = "0"
    atuacao_area: str = "0"
    atuacao_subarea: str = "0"
    atuacao_especialidade: str = "0"
    orientacao: list[str] = field(default_factory=list)              # IC, IP, ME, DA, DH
    idioma: str = "0"
    producao_grande_area: str = "0"
    producao_area: str = "0"
    producao_setor: str = "0"
    atividade_pais: str = "0"
    atividade_regiao: str = "0"
    atividade_uf: str = "0"
    atividade_instituicao: str = ""
    atividade_natureza: str = "0"
    atividade_atual: bool = False
    presente_dgp: bool = False

    # --- serialização ---
    def para_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def de_dict(cls, d: dict | None) -> "FiltrosBusca":
        f = cls()
        validos = {x.name for x in fields(cls)}
        for k, v in (d or {}).items():
            if k in validos:
                setattr(f, k, v)
        return f

    def copia(self, **mudancas) -> "FiltrosBusca":
        d = self.para_dict()
        d.update(mudancas)
        return FiltrosBusca.de_dict(d)

    # --- caixas de filtro marcadas ---
    def caixas(self) -> dict[int, bool]:
        return {
            0: bool(self.bolsa_categorias),
            1: self.bolsa_modalidade not in ("", "0"),
            2: any(v not in ("", "0") for v in (self.formacao_nivel, self.formacao_pais, self.formacao_regiao,
                                                 self.formacao_uf)) or bool(self.formacao_instituicao),
            3: bool(self.conceito_curso),
            4: self.atuacao_grande_area not in ("", "0"),
            5: bool(self.orientacao),
            6: self.idioma not in ("", "0"),
            7: any(v not in ("", "0") for v in (self.producao_grande_area, self.producao_area, self.producao_setor)),
            8: any(v not in ("", "0") for v in (self.atividade_pais, self.atividade_regiao, self.atividade_uf,
                                                 self.atividade_natureza)) or bool(self.atividade_instituicao)
               or self.atividade_atual,
            9: self.presente_dgp,
        }

    def resumo(self) -> list[str]:
        """Frases curtas descrevendo o que está ativo (para revisão e listagens)."""
        r = []
        bases = [n for n, ok in (("Doutores", self.doutores), ("Demais pesquisadores", self.demais)) if ok]
        r.append("Bases: " + (", ".join(bases) or "nenhuma"))
        if self.texto:
            r.append(f"{'Nome' if self.modo == 'nome' else 'Assunto'}: {self.texto}")
        if not (self.brasileiros and self.estrangeiros):
            r.append("Nacionalidade: " + ("brasileira" if self.brasileiros else "estrangeira"))
        if self.atualizacao_meses:
            r.append(f"Atualizados nos últimos {self.atualizacao_meses} meses")
        if self.bolsa_categorias:
            r.append("Bolsa de produtividade: " + ", ".join(self.bolsa_categorias))
        if self.bolsa_modalidade not in ("", "0"):
            r.append("Bolsista CNPq: " + rotulo("modalidadeBolsa", self.bolsa_modalidade))
        form = [rotulo("nivelFormacao", self.formacao_nivel) if self.formacao_nivel != "0" else "",
                rotulo("ufs", self.formacao_uf) if self.formacao_uf != "0" else "",
                rotulo("regioes", self.formacao_regiao) if self.formacao_regiao != "0" else "",
                rotulo("paises", self.formacao_pais) if self.formacao_pais != "0" else "",
                self.formacao_instituicao]
        if any(form):
            r.append("Formação: " + " · ".join(x for x in form if x))
        if self.conceito_curso:
            r.append("Conceito do curso: " + ", ".join(self.conceito_curso))
        area = self.atuacao_especialidade if self.atuacao_especialidade != "0" else (
            self.atuacao_subarea if self.atuacao_subarea != "0" else (
                self.atuacao_area if self.atuacao_area != "0" else self.atuacao_grande_area))
        if area not in ("", "0"):
            r.append("Área de atuação: " + " > ".join(n["texto"] for n in buscar_area(area)))
        if self.orientacao:
            r.append("Orientação: " + ", ".join(catalogo().get("orientadorCNPq", {}).get(o, o) for o in self.orientacao))
        if self.idioma not in ("", "0"):
            r.append("Idioma: " + rotulo("idiomas", self.idioma))
        if self.producao_grande_area != "0" or self.producao_setor != "0":
            r.append("Produção C&T: " + " · ".join(x for x in (
                rotulo("grandesAreas", self.producao_grande_area) if self.producao_grande_area != "0" else "",
                rotulo("setoresProducao", self.producao_setor) if self.producao_setor != "0" else "") if x))
        ativ = [rotulo("ufsAtividade", self.atividade_uf) if self.atividade_uf != "0" else "",
                rotulo("regioesAtividade", self.atividade_regiao) if self.atividade_regiao != "0" else "",
                rotulo("paises", self.atividade_pais) if self.atividade_pais != "0" else "",
                rotulo("naturezaAtividade", self.atividade_natureza) if self.atividade_natureza != "0" else "",
                self.atividade_instituicao, "atual" if self.atividade_atual else ""]
        if any(ativ):
            r.append("Atividade profissional: " + " · ".join(x for x in ativ if x))
        if self.presente_dgp:
            r.append("Presente no Diretório de Grupos de Pesquisa")
        return r

    # --- tradução para o formulário do CNPq ---
    def para_formulario(self, por_pagina: int = 100) -> dict:
        """Campos (name -> valor), checkboxes (id -> bool) e funções do site a chamar."""
        assunto = self.modo == "assunto"
        campos = {
            "textoBusca": self.texto,
            "filtros.buscaNome": "true" if not assunto else "false",
            "filtros.buscaAssunto": "true" if assunto else "false",
            "paisNascimento": self.pais_nascimento or "0",
            "filtros.atualizacaoCurriculo": str(self.atualizacao_meses or ""),
            "quantidadeRegistros": str(por_pagina),
            "filtros.categoriaNivelBolsa": "".join(f"{c}," for c in self.bolsa_categorias),
            "filtros.modalidadeBolsa": self.bolsa_modalidade or "0",
            "filtros.nivelFormacao": self.formacao_nivel or "0",
            "filtros.paisFormacao": self.formacao_pais or "0",
            "filtros.regiaoFormacao": self.formacao_regiao or "0",
            "filtros.ufFormacao": self.formacao_uf or "0",
            "filtros.nomeInstFormacao": self.formacao_instituicao,
            "filtros.conceitoCurso": "".join(f"{c}," for c in self.conceito_curso),
            "filtros.codigoGrandeAreaAtuacao": self.atuacao_grande_area or "0",
            "filtros.codigoAreaAtuacao": self.atuacao_area or "0",
            "filtros.codigoSubareaAtuacao": self.atuacao_subarea or "0",
            "filtros.codigoEspecialidadeAtuacao": self.atuacao_especialidade or "0",
            "filtros.buscaAtuacao": "true" if self.atuacao_grande_area not in ("", "0") else "false",
            "filtros.orientadorCNPq": "".join(f"{c}," for c in self.orientacao),
            "filtros.idioma": self.idioma or "0",
            "filtros.grandeAreaProducao": self.producao_grande_area or "0",
            "filtros.areaProducao": self.producao_area or "0",
            "filtros.setorProducao": self.producao_setor or "0",
            "filtros.paisAtividade": self.atividade_pais or "0",
            "filtros.regiaoAtividade": self.atividade_regiao or "0",
            "filtros.ufAtividade": self.atividade_uf or "0",
            "filtros.nomeInstAtividade": self.atividade_instituicao,
            "filtros.naturezaAtividade": self.atividade_natureza or "0",
        }
        checks = {
            "buscaNome": not assunto, "buscaAssunto": assunto,
            "buscarDoutores": self.doutores, "buscarDemais": self.demais,
            "buscarBrasileiros": self.brasileiros, "buscarEstrangeiros": self.estrangeiros,
            "atividadeatual": self.atividade_atual, "participaDGP": self.presente_dgp,
        }
        for i, marcado in self.caixas().items():
            checks[f"filtro{i}"] = marcado
        for c in ("1A", "1B", "1C", "1D", "2", "A", "B", "C"):
            checks[f"checkbox{c}"] = c in self.bolsa_categorias
        for c in "1234567":
            checks[f"checkConceito{c}"] = c in self.conceito_curso
        for c in ("IC", "IP", "ME", "DA", "DH"):
            checks[f"checkbox{c}"] = c in self.orientacao
        return {"campos": campos, "checks": checks}


# Script que roda na página de busca do CNPq para preencher o formulário. Para selects
# em cascata (área > subárea...), cujas opções só chegam por AJAX, cria a opção se
# faltar. Depois chama as funções do próprio site que montam os campos ocultos.
JS_PREENCHER = r"""
const dados = arguments[0];
const form = document.getElementById('id_form_busca') || document.forms['buscaForm'] || document.forms[0];
const faltando = [];
for (const [nome, valor] of Object.entries(dados.campos)) {
  const els = form.querySelectorAll('[name="' + nome + '"]');
  if (!els.length) { faltando.push(nome); continue; }
  for (const el of els) {
    if (el.type === 'checkbox' || el.type === 'radio') continue;
    if (el.tagName === 'SELECT' && valor !== '' && ![...el.options].some(o => o.value === valor)) {
      el.add(new Option(valor, valor));
    }
    el.value = valor;
  }
}
for (const [id, marcado] of Object.entries(dados.checks)) {
  const el = document.getElementById(id);
  if (el) el.checked = !!marcado; else faltando.push('#' + id);
}
for (const fn of ['preencheCategoriaNivelBolsa', 'preencheConceitoCurso', 'preencheOrientacao']) {
  try { if (typeof window[fn] === 'function') window[fn](); } catch (e) {}
}
// as funções acima reescrevem os ocultos; garante o valor final escolhido
for (const nome of ['filtros.categoriaNivelBolsa', 'filtros.conceitoCurso', 'filtros.orientadorCNPq']) {
  const el = form.querySelector('[name="' + nome + '"]');
  if (el) el.value = dados.campos[nome];
}
return faltando;
"""

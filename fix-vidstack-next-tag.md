# Fix: `@vidstack/react@next` causa crash del build con Reflex 0.9.3

## Problema

Il build fallisce con:

```
RollupError: Failed to parse source for import analysis because the
content contains invalid JS syntax.
[PARSE_ERROR] Unexpected JSX expression
node_modules/@vidstack/react/prod/player/vidstack-default-icons.js
```

La causa è nel file `StepDaddyLiveHD/components/media_player.py`, riga 7:

```python
lib_dependencies: list[str] = ["@vidstack/react@next"]
```

Il tag `@next` installa sempre l'ultima versione **unstable** di `@vidstack/react`,
che distribuisce file `.js` con JSX raw non compilato.
Vite/Rolldown (usato da Reflex) **non accetta JSX in file `.js`** — si aspetta `.jsx` o `.tsx`.

## File da modificare

`StepDaddyLiveHD/components/media_player.py`

## Modifica da apportare

### Prima (riga 7)

```python
lib_dependencies: list[str] = ["@vidstack/react@next"]
```

### Dopo

```python
lib_dependencies: list[str] = ["@vidstack/react@1.12.11"]
```

## Perché questa versione

`1.12.11` è l'ultima versione **stabile** del branch 1.x, compatibile con
la toolchain di Reflex 0.9.3 (Vite 6 + Rolldown).

Le versioni `@next` (2.x) usano una build moderna con JSX non precompilato
che Rolldown non riesce a parsare nei file `.js`.

## Nessuna altra modifica necessaria

| Suggerimento ChatGPT | Necessario? | Motivo |
|---|---|---|
| Downgrade `@vidstack/react` | ✅ Sì | È il fix corretto |
| Forzare React 18 | ❌ No | Non è la causa del problema |
| Aggiornare Reflex oltre 0.9.3 | ❌ No | 0.9.3 funziona correttamente con questa fix |

## Riepilogo

| File | Riga | Prima | Dopo |
|---|---|---|---|
| `StepDaddyLiveHD/components/media_player.py` | 7 | `"@vidstack/react@next"` | `"@vidstack/react@1.12.11"` |
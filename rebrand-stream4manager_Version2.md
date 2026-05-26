# Rebrand visivo: StepDaddyLiveHD → Stream4Manager

## Obiettivo

Cambiare solo le stringhe di testo **visibili all'utente** nel frontend.
Nessuna modifica a import, nomi di classi, file, cartelle o logica.

---

## Modifiche

### 1. `rxconfig.py`

```python
# PRIMA
app_name="StepDaddyLiveHD",

# DOPO
app_name="Stream4Manager",
```

> Questo aggiorna automaticamente il titolo nella navbar sia desktop
> che mobile, poiché entrambi usano `config.app_name`.

---

### 2. `StepDaddyLiveHD/pages/playlist.py`

```python
# PRIMA
rx.heading("Welcome to StepDaddyLiveHD", size="7", margin_bottom="1rem"),

# DOPO
rx.heading("Welcome to Stream4Manager", size="7", margin_bottom="1rem"),
```

```python
# PRIMA
"StepDaddyLiveHD allows you to watch various TV channels via IPTV. "

# DOPO
"Stream4Manager allows you to watch various TV channels via IPTV. "
```

---

## File da NON toccare

Tutto il resto.
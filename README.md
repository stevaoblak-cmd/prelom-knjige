# Prelom knjige

Program za prelom teksta za štampu. Uvezete Word (.docx) ili PDF, proverite tekst,
podesite format i dobijete PDF spreman za štampariju.

## Šta ume

- **Uvoz**: Word (.docx) sa naslovima, kurzivom i podebljanim; PDF (spaja redove u pasuse,
  uklanja deljenje reči na kraju reda, brojeve strana i ponavljajuća zaglavlja); .txt.
- **Format strane**: A4, A5, B5, B6, 13×20, 14×20, 14,5×20,5, 16,5×23,5, 17×24, 20×20 cm ili proizvoljno.
- **Margine**: gore, dole, unutrašnja (uz povez) i spoljna, ogledalno za leve i desne strane.
- **Slova**: bilo koji instalirani font + dodavanje sopstvenog .ttf/.otf, veličina, prored,
  uvlaka pasusa, razmak između pasusa, obostrano poravnanje.
- **Automatsko deljenje reči** za srpski (ćirilica i latinica, pismo se prepoznaje samo).
- **Poglavlja** počinju na neparnoj (desnoj) strani: program sam ubacuje praznu stranu kad treba.
- **Udovice i siročići**: pasus ne ostavlja jedan red sam na vrhu ili dnu strane.
- **Paginacija i živa glava**: broj strane spolja ili u sredini, naslov knjige na levoj
  i naslov poglavlja na desnoj strani; prazne i početne strane poglavlja ostaju čiste.
- **Naslovna strana** i **automatski sadržaj** sa brojevima strana.
- **Za štampariju**: dopuna praznim stranama do umnoška 4/8/16/32 (tabaci), oznake za sečenje, prepust (bleed).
- Čuvanje i otvaranje projekta (tekst + podešavanja u jednoj .json datoteci).

## Oznake u tekstu

```
# Naslov poglavlja          novo poglavlje
## Podnaslov                naslov odeljka
### Manji naslov
*kurziv*  **podebljano**
* * *                       razmak između scena
> citat                     uvučen citat
[nova strana]               prelom strane
[prazna strana]             ubacuje praznu stranu
[neparna strana]            nastavlja na sledećoj neparnoj strani
```
Pasusi se razdvajaju praznim redom.

## Pokretanje

Potreban je Python 3.10+.

**Linux / macOS**: `./pokreni.sh` (macOS: prethodno `brew install pango`).

**Windows**: WeasyPrint koristi biblioteku Pango, koja se instalira jednom:
1. Instalirati MSYS2 sa https://www.msys2.org
2. U MSYS2 terminalu: `pacman -S mingw-w64-x86_64-pango`
3. Dvoklik na `pokreni.bat`.

Program se otvara u pregledaču na adresi http://127.0.0.1:5000

## Struktura

- `prelom/importers.py` – uvoz Word / PDF / TXT
- `prelom/layout.py` – podešavanja, prelom zapis → HTML/CSS → PDF (WeasyPrint)
- `app.py`, `templates/index.html` – interfejs

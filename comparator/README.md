# Comparator - Primerjava datotek

Program za primerjavo datotek med dvema direktorijema in generiranje CSV poročila o razlikah.

## Funkcionalnosti

- Primerja vse datoteke z istim imenom med dvema direktorijema
- Zapiše datoteke, ki so enake
- Zapiše datoteke, ki so različne, skupaj s podrobnostmi o razlikah
- Zapiše datoteke, ki obstajajo samo v enem direktoriju
- Ustvari CSV poročilo z vsemi razlikami

## Zahteve

- Python 3.6 ali novejši

## Uporaba

```
python comparator.py direktorij1 direktorij2 [--output izhodna_datoteka.csv]
```

### Parametri:

- `direktorij1`: Prvi direktorij za primerjavo
- `direktorij2`: Drugi direktorij za primerjavo
- `--output` ali `-o`: Pot do izhodne CSV datoteke (privzeto: razlike.csv)

### Primer:

```
python comparator.py "ESCO dataset - v1.0.7 - classification - en - csv" "ESCO dataset - v1.2.0 - classification - en - csv (3)" --output esco_razlike.csv
```

## Format izhodne datoteke

CSV datoteka vsebuje naslednje stolpce:
- **Relativna pot**: Pot do datoteke, relativna glede na vhodni direktorij
- **Status**: Eden od naslednjih statusov:
  - "Enaki" - datoteki sta identični
  - "Različni" - datoteki sta različni
  - "Samo v dir1" - datoteka obstaja samo v prvem direktoriju
  - "Samo v dir2" - datoteka obstaja samo v drugem direktoriju
- **Podrobnosti**: Za različne datoteke vsebuje vse razlike med datotekama
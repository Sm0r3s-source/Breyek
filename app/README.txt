Breyek 3.0.0 - akių pertraukų asistentas (be DI ir be mašininio mokymosi)

Paleidimas iš kodo:  py -m pip install -r requirements.txt
                     py breyek.py           (20 min / 5 min / 1 min)
                     py breyek.py --test    (demo: 20 s / 5 s / 10 s)
.exe sukūrimas:      dukart spustelėti build.bat -> dist\Breyek-2.0.exe ir dist\Breyek-2.0-Demo.exe
Avarinis išėjimas pertraukos metu: laikyti Ctrl+Alt+Shift ir paspausti Q.

Visi failai turi būti viename aplanke: breyek.py, screen_activity.py, aplankas lang/ (40 kalbų),
breyek.ico, breyek-demo.ico, sponsor_lik_light.png, sponsor_lik_dark.png.

Privatumas
- Pirmą kartą paleidus (ir pakeitus politiką – POLICY_VERSION) programa paprašo sutikti su privatumo
  politika ir naudojimo sąlygomis: https://breyek-api.breyek-api.workers.dev/privacy
  Be sutikimo programa neveikia. Dalijimasis duomenimis tame lange – atskiras, neprivalomas pasirinkimas.
- Pagal nutylėjimą niekas iš kompiuterio neišsiunčiama ir niekas nekaupiama.
- Skiltyje „Privatumas“ naudotojas gali pats įjungti dalijimąsi anoniminiais duomenimis
  (versija, kalba, tema, pertraukų skaičius, naudojimo minutės ir minutės pagal veiklos tipą). Išjungus duomenys ištrinami.
- Siuntimas veikia tik tada, kai breyek.py faile TELEMETRY_URL nurodytas jūsų serverio adresas.
  Kol jis tuščias, duomenys lieka tik naudotojo kompiuteryje (%APPDATA%\Breyek-2.0\usage.json).

Rėmėjai
- Sąrašas SPONSORS faile breyek.py: (pavadinimas, logotipo failas be _light/_dark.png galūnės).
- Logotipas rodomas pertraukos metu ir skiltyje „Rėmėjai“. Kiekvienam rėmėjui reikia dviejų PNG:
  *_light.png (šviesus, tamsiam fonui) ir *_dark.png (tamsus, šviesiam fonui), apie 56 px aukščio.

Kalbos: kiekviena kalba yra atskiras failas lang/<kodas>.json (pavadinimas, tekstai, 9 patarimai).
Norint pataisyti vertimą, užtenka pakeisti tą failą; trūkstami tekstai rodomi angliškai.
Pirmą kartą paleidus parenkama „Windows“ kalba (jei jos nėra – anglų).

Pertraukos metu programa sustabdo grojančius vaizdo įrašus ir muziką (YouTube naršyklėje, Spotify ir kt.)
per „Windows“ medijos valdiklius, o po pertraukos paleidžia būtent juos. Išjungiama nustatymuose.

Statistika (skiltis „Statistika“): savaitės grafikas, kiek laiko praleista prie kompiuterio ir ką darėte
(rašymas, pelė, visas ekranas / žaidimai, vaizdo įrašai, skaitymas). Nustatoma tik pagal įvesties tipą ir
ekrano judėjimą. Saugoma %APPDATA%\Breyek-2.0\stats.json (60 dienų). Dienų sumos siunčiamos tik
jei naudotojas įjungė dalijimąsi duomenimis.

Kontaktai: breyek@protonmail.com (klaidos – [Bug], pagalba – [Support], rėmėjai ir partneriai – [Partner]).

Breyek Pro (1,99 € / mėn. arba 15,99 € / metams, per Polar)
- Pro: savi laikmačiai ir šablonai (20/1, 25/5, 50/10), išmani pauzė skambučių ir viso ekrano programų metu
  (iki 10 min.), įspėjimas 30 s prieš pertrauką su atidėjimu (2 kartai per dieną), 30 dienų statistika ir
  CSV eksportas (saugoma metus), vakarinis akių filtro grafikas, 3 papildomos temos, garsai, akių pratimai,
  be rėmėjų pertraukos metu.
- Kodas: pro.py. Kol POLAR_ORG_ID tuščias, veikia bandomasis raktas BREYEK-TEST-PRO.
- Paleidžiant tikrai: pro.py užpildyti POLAR_ORG_ID, PRO_BUY_URL, PRO_PORTAL_URL (žr. žemiau).

Polar paruošimas
1. Susikurti paskyrą https://polar.sh (breyek@protonmail.com) ir organizaciją „Breyek“.
2. Products -> New product „Breyek Pro“: kaina 1,99 € kas mėnesį. Antras produktas: 15,99 € kas metus.
3. Abiem produktams Benefits -> License Keys (vienas ir tas pats benefit).
4. Checkout Links -> nauja nuoroda su abiem produktais -> nukopijuoti į PRO_BUY_URL.
5. Settings -> General: Organization ID -> į POLAR_ORG_ID. PRO_PORTAL_URL = https://polar.sh/<org-slug>/portal
6. Pirmiausia viską išbandyti sandbox.polar.sh (netikri mokėjimai, pro.py: POLAR_SANDBOX = True),
   tada tą patį padaryti tikroje polar.sh paskyroje ir grąžinti POLAR_SANDBOX = False.

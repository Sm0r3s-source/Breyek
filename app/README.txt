Breyek 2.5.0 - akių pertraukų asistentas (be DI ir be mašininio mokymosi)

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

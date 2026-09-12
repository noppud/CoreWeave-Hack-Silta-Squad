# Training LLM Agents with OpenPipe

- **Source:** Wispr Flow meeting recorder
- **Recorded:** September 12, 2026, 11:43 AM PDT (two segments; second resumed 11:57 AM)
- **Owner:** Konsta Varonen
- **Language:** mixed Finnish and English, transcribed verbatim

Working record of the session where the CNC process-planning agent idea took
shape. Kept as-is, including transcription errors. Known garbling: "OpenVet" is
OpenPipe, "Stastra"/"Astra kutonen" is Astra 6, "WIM"/"weavel" refers to the
Weights & Biases mentor, "Marivo" is marimo, "NX" is Siemens NX.

## Summary

### Flow Summary

Keskustelu OpenPipen ART-frameworkista agenttien RL-treenaukseen, ja CNC-osien
valmistusta suunnittelevan AI-agentin demon hahmottelu, mukaan lukien
simulaatio-osuus.

### ART / OpenPipe -keskustelu

- ART (OpenPipe): open source framework LLM-agenttien RL-treenaukseen multi-step-tehtävissä
- Oppiminen mm. muokkaamalla step- ja tool-call-järjestystä, experience-driven reliability
- Jos halutaan reinforcement learning omalle mallille, Astraa ei voi käyttää

### CNC AI -agentin demo

- Multimodaalinen input (PDF, kuvat, teksti, CAD); output = 'resepti' osan valmistamiseen
- Käyttäjä listaa koneet ja työkalut; simulaatio varmistaa reseptin toimivuuden
    - Simulaatio kallista, tarkistuksia siirretään halvempiin testeihin
- Demoon visuaalinen 3D-simulaatio koneesta poraamassa osaa, ensin epäonnistuu, sitten onnistuu
- Optimointi voi vähentää osan kääntöjä ja alentaa kustannuksia

### Seuraavat askeleet

- (Speaker 1) Kysyä asiakkaalta, halutaanko treenata omaa mallia / muokata weightteja
- (Speaker 1) Kysyä käytetäänkö OpenVet-malleja vai Astra 6 / Fable, ja mitä trend feedistä saataisiin business caseen
- (Speaker 2) Tutkia CNC-agentin output-formaattia ja rakennetta tarkemmin ennen toteutusta

## Transcript

```text
[00:00] Speaker 1: Blender, Python, generators. Okay.
[00:54] Speaker 1:  Mä en oo ik
[00:55] Speaker 2: inä syönyt sillä tavalla, että mä treenaan omaa mallia.
[00:58] Speaker 1:  Ei mun mielestä tarvi treenaa omaa mallia.
[00:59] Speaker 2:  Kun se puhui siitä, tästä ART, Agent Reinforcement Trainerista, niin se puhui siitä monta kertaa.
[01:05] Speaker 1:  Se on mun mielestä meinaa vaan sitä, että sä treenaat, tai niinku, että sillä agentilla on feedback loop, ja että sä muutat sen agentin parametreja.
[01:14] Speaker 2:  Se on mikä toi ART framework, se itse sanoi. Niin se puhui siitä monta kertaa.
[01:18] Speaker 1:  Just niinku—
[01:18] Speaker 2:  Mä—
[01:20] Speaker 1:  Joo, mikä toi framework oli?
[01:21] Speaker 2:  Ei ART, Agent Reinforcement Trainer, vaan OpenPipe. ART, OpenPipe. Open source framework designed to train and improve LLM-based agents on multi-step tasks using reinforcement learning.
[01:36] Speaker 1:  Niin, se kyllä kuulostaa siltä.
[01:40] Speaker 2:  Se WIM-tyyppi nimenomaan puhui tosta.
[01:41] Speaker 1:  Joo, joo, mutta tää on niinku experience-driven reliability, eli moves beyond rigid prompt engineering by letting agents learn from trial and error over multi-step workflows.
[01:54] Speaker 2:  Ja miten se oppiminen menee siinä?
[01:57] Speaker 1:  No esimerkiksi sillä, että se muokkaa vaan, missä järjestyksessä sä saat tehdä niitä eri steppejä. Tai tool-calleja, mun mielestä.
[02:07] Speaker 2:  Okei, okei. No mut hei, me ei kysy joo, koska noi on—
[02:10] Speaker 1:  Me ei vaan kysytä, että haluuks ne nyt, tota, että me treenataan joku modelli vai— Koska sit jos on nyt se, että halutaan reinforcement learnoa jotain OpenVet-mallia, niin sit me ei voida käyttää Stastraa esimerkiksi.
[02:23] Speaker 2:  Niin, ei toi— Ehkä ne kyselee, että halutaanko me muokata niitä weightteja vai vaan niinku—
[02:29] Speaker 1:  No sä voit kans kysyä, että onko referenssit, käytetäänkö jotain OpenVet-malleja vai Astra kutosta tai Fablea.
[02:36] Speaker 2:  Joo. Mä kysyn sit toisaalta, jos sä sanoit, että sä haluaisit, että me käytetään OpenVet-malleja, niin kysy kait siitä, mitä meidän trend feedistä saatais tässä business casessa sitten.
[02:45] Speaker 1:  Joo, mä kysyn.
[02:48] Speaker 2:  Ja ota tää mukaan.
[02:51] Speaker 1:  NX, mä sanon.
[02:52] Speaker 2:  Joo, laita tää.
[02:53] Speaker 1:  Joo, NX.
[02:54] Speaker 2:  Onko se päällä?
[02:55] Speaker 1:  Laita vaan tänne.
[02:58] Speaker 2:  Noin.
[04:10] Speaker 1:  Jep. Okei, so we're building an AI agent that does CNC parts.
[04:16] Speaker 2:  Yeah. So a CNC shop, they receive like some PDFs and a question like, "Can you build this for us?"
[04:22] Speaker 1:  And it's multi-modal, so it takes like images, PDFs, all the fucking shit.
[04:27] Speaker 2:  Yeah, text.
[04:28] Speaker 1:  Text, yeah.
[04:29] Speaker 2:  Maybe something else, like a CAD file or something. Then the agent starts, like, kind of thinking of, "How do you do it?" They have to do, like, the CAD file of the part and also the kind of step files, like the instructions.
[04:46] Speaker 2:  I'm not, like, "This has to be researched more."
[04:51] Speaker 1:  Uh, so what's like the format that it outputs?
[04:53] Speaker 2:  I'm not quite sure, but it's some, it's like the recipe for making the part.
[04:57] Speaker 1:  Okay. And in the demo, we basically have some sort of input, like an UI or a chat agent, and the user will ask, like, "Hey, I have this snooze, can you build a holder for this?"
[05:11] Speaker 2:  Yeah.
[05:12] Speaker 1:  And then they can also take a picture, and that's submitted, and then the agent will spin and output, like, instructions on how to actually get this manufactured.
[05:22] Speaker 2:  Yeah, yeah, like—
[05:23] Speaker 1:  So did I, like, understand this correctly?
[05:24] Speaker 2:  Yeah, pretty much. Or maybe you, like, send the kind of PDFs of the part. Not like, because we don't want to, the agent we're building is not necessarily good at, like, designing the part from zero, but once you have, like, the drawings of kind of what you want to do, the agent is good at figuring out, like, how it should be built.
[05:43] Speaker 2:  And then, like, depending, you have, like, different machines in the shop, and not every machine can do, like, every hole and every kind of accuracy and stuff like that. So we could have a thing where it's like, "List all your machines here and the tools you have," and then we have, like, a simulation that makes sure that the kind of recipe you provided actually works with the machines you have.
[06:15] Speaker 2:  And then if it doesn't work, because simulation is kind of expensive, we want to move those checks to the kind of, uh, the tests that are, like, cheaper to run, at least. And then we improve that flow so that we have to simulate as little as possible, and then eventually it will be really good.
[06:35] Speaker 1:  Yeah, that's great. Awesome. Super awesome.
[06:41] Speaker 2:  Yes.
[06:42] Speaker 1:  Do you think Astra 6 will implement this if we just give this context and this screenshot?
[06:49] Speaker 2:  I think we have to, like, uh, I'm not sure. Let's look at this a bit more. And then once we have this, it's like actually in a state that we understand it fully.
[07:01] Speaker 1:  Okay, let's look at it.
[07:02] Speaker 2:  Then we can start building.
[07:03] Speaker 1:  Yeah, I think—
[07:04] Speaker 2:  And then also, for the demo, I want there to be actually a visual simulation of it trying to drill the machine, the part, with the machine.
[07:15] Speaker 1:  So we need some form of, like, simulation about the machine.
[07:20] Speaker 2:  Yeah, yeah, yeah.
[07:21] Speaker 1:  I don't know how the fuck do we do that.
[07:23] Speaker 2:  Astra can do it, for sure.
[07:25] Speaker 1:  Okay, okay.
[07:26] Speaker 2:  But it's going to be super cool since it's going to try to do it. Then we show, like, first time didn't work, then but then eventually every part goes through, like, and it's even, like, I think there can be, like, a single recipe can be, like, more efficient if you have to turn the part less and, like, grow with the same tool, do, like, multiple holes in a row, and so on. So there's a lot of stuff to improve on.
[07:54] Speaker 1:  Yeah, yeah.
[07:54] Speaker 2:  Like, you can even get the cost down if it's, like, faster to build that specific part.
[08:00] Speaker 1:  Yeah.
[08:01] Speaker 2:  So we're going to, like, double probably revenue, profits.
[08:06] Speaker 1:  Yeah, that's, that's amazing.
[08:08] Speaker 2:  And it's going to be 3D and cool, and maybe even— yeah, okay. Let's, let's do this first.
[08:18] Speaker 1:  Okay.

[11:57 AM] -- Resumed --

[0:01] Speaker 3: Öö, liikkuu ihan miten tahansa.
[0:05] Speaker 3:  Niin se oikeasti pitää kanssa miettiä, että se miten se suunnittelee, se oikeasti sopii siihen.
[0:06] Speaker 4:  Joo.
[0:12] Speaker 3:  Ja sitten me näytetään vaikka first round, se alkaa tekemään sitä, se niinku menee ihan plörinäksi.
[0:12] Speaker 4:  Joo.
[0:19] Speaker 3:  Ja sitten niinku final round, kun se looppia on pyörinyt pari kertaa, niin boom, se vaan boom, broom, broom, broom, broom, ja sieltä tulee valmis osa.
[0:21] Speaker 4:  Joo.
[0:24] Speaker 4:  Sano heti kun sä oot pannut sitten niinku ajettua.
[0:25] Speaker 3:  Joo.
[0:26] Speaker 4:  Sisään.
[0:30] Speaker 3:  Siinä oli, mä en sitten osaa kertoa paremmin, kun mä muistan mitä se kertoi, kun mä—
[0:37] Speaker 4:  Mutta hyvä, voitko sä jotenkin kanssa invaittaa mun, öö, kun mä en ole tätä niinku transcriptiä, mä näen vaan ton summaryn.
[0:38] Speaker 3:  Ai tosta?
[0:39] Speaker 4:  Tästä, öö, meidän keskustelusta.
[0:40] Speaker 3:  Mä tiedän sen.
[0:41] Speaker 4:  Mun ja Konstan kanssa.
[0:42] Speaker 3:  Siis mitä, mitä, mitä?
[0:45] Speaker 4:  Älä, en mä tiedä onko se niin deep, tää on ihan hyvä.
[0:47] Speaker 3:  Mä voin laittaa sen tuonne GitHubiin suoraan.
[0:48] Speaker 4:  Joo, joo, joo. Joo.
[0:50] Speaker 4:  Laita vaan suoraan.
[0:52] Speaker 3:  Joo.
[0:56] Speaker 4:  Mutta se oli sitä mieltä, että meidän kannattaa toi, siis arjessa me voidaan voittaa.
[0:57] Speaker 3:  Joo.
[0:59] Speaker 4:  Mutta hyvä tää äijä on, miten se on niin—
[1:02] Speaker 3:  Se oli weavel, se oli se, se on niinku weavel, se ei ole niinku judge, mutta se on se niinku niin.
[1:03] Speaker 4:  Joo.
[1:08] Speaker 3:  Se on kyllä aika hyvä, se antaa aika hyvää vinkkiä, mutta se arjaa vaan viis tulee, tai sitten me saadaan kyllä.
[1:08] Speaker 4:  Ei sulle tonni.
[1:09] Speaker 3:  Aa.
[1:09] Speaker 4:  Joo.
[1:11] Speaker 3:  Ai niin, mi.
[1:14] Speaker 4:  Se Marivo oli, Marimo, Marimo oli 5 tonnia.
[1:15] Speaker 3:  Meillä on, mikä oli Marimo?
[1:17] Speaker 4:  Se oli se Pyton librari, missä voitaisiin demo.
[1:19] Speaker 3:  Oo, niin se.
[1:23] Speaker 4:  Mutta kyllä me se demo varmaan sieltä tehdään, mutta en mä, en mä tiedä, meidän kannattaa ehkä optimoida vaan sitä niinku aikaa.
[1:27] Speaker 3:  Niin, ja kyllä se voi olla, että jos meillä on vaikka ihan sairas demo, missä on niitä machineja oikeasti siellä.
[1:28] Speaker 4:  Joo.
[1:30] Speaker 3:  Missä on niinku Marimo-tyyppi, menee sekaisin.
[1:36] Speaker 4:  Niin, niin, että se on vaan sille hyvä, että me vaan, se on, se on vaan niinku collateral käytännössä, se voitto.
[1:37] Speaker 3:  Joo.
[1:38] Speaker 4:  Että sitä ei todellakaan kannata optimoida.
[1:39] Speaker 3:  Onko se GitHubissa nyt?
[1:40] Speaker 4:  Öö, ei vielä.
[1:45] Speaker 3:  Okei, okei, okei. Öö, pull, pull, the newest plug.
[1:45] Speaker 4:  Joo.

[11:59 AM] -- Paused --

[1:50] Speaker 3:  Oota, mä mietin, mietin hetken, luulisin, että.
```

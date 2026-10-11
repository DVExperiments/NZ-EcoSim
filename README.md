NZ ECOSIM
=========
A miniature island ecosystem that lives in a desktop window - an overly complex,
overly realistic tamagotchi set in New Zealand.  The island starts as Aotearoa
before people: forest, wetlands, tussock high country, and birds that evolved
with no land mammals.  Add species, land settlers, bend the physics, or leave it
alone - and learn why things happen from clickable alerts.


PUT IT ON THE WEB
-----------------
See HOSTING.txt: a free website (GitHub Pages) with a locked live island that keeps living
long-term, plus an unlocked copy of the simulation that runs in any browser tab.


HOW TO START (Windows)
----------------------
1. Install Python 3 from https://www.python.org/downloads/
   (on the first installer screen, tick "Add python.exe to PATH").
2. Double-click  "Run NZ EcoSim.bat"  (first run installs pygame + numpy).
   Or double-click nz_ecosim.py, or run:  python nz_ecosim.py
3. Optional: "Build EXE.bat" makes a standalone dist\NZ EcoSim.exe.

Saves from earlier versions can't be loaded, so the first launch opens the
island generator.


NEW ISLAND (press N, or the "New" button)
----------------------------------------
Every island is generated fresh. Choose:
  Region      North Island (warmer, kauri, more kiwi & tui) or South Island
              (colder, beech forest, tussock high country, takahe, more kakapo)
  Geography   Big island, Small islands, Mountainous, Lowlands, Lakes & wetlands
  Tweaks      land area, mountains, starting forest cover, rainfall
  Seed        "New random seed" for a different layout; the preview updates live


TIME AND REALISM
----------------
Real calendar: 365-day years, months and southern-hemisphere seasons
(e.g. "Year 2 - 14 Mar - Autumn").  A day passes in about 4 seconds at 1x.

Life runs 20x faster than the calendar: each calendar year, every animal and
person lives about 20 years of its life.  The SAME factor is used for every
species, and lifespans, age at first breeding, litter/clutch sizes and
breeding seasons come from real New Zealand data (DOC, Te Ara, Landcare
Research), so species keep their true pace relative to each other:
  - a ship rat lives about a year and breeds 3-5 times a year; a kiwi lives
    35 years and lays 1-2 eggs a year; a kakapo lives 75 years and breeds only
    in mast years, every 2-5 years
  - people grow up, and the clan's children only work once they turn 16; with
    plenty of food a settlement grows about 1-3% a year, as Aotearoa's first
    settlers did
  - introduced predators mostly kill eggs, chicks and young (as in real life);
    the last few of a rare species are harder to find, so declines take
    decades of "life time", not days
Ages shown on the info cards are biological ages.

DIFFICULTY (Learn tab, the New island window, or the lesson picker)
  Gentle     slower pests and settlers, hardier birds, fewer voyages
  Realistic  real-world life history and growth rates (the default)
  Harsh      pests at the top of their natural range, more ships, warlike clans


LESSONS (press L, or the Learn tab)
-----------------------------------
Ready-made challenges based on real NZ conservation stories.  Each builds a new
island, shows its goals on the map (top right) and ends with a debrief: what
happened, what killed the native wildlife, what you did, and the real story.
  Save the kakapo        protect the last 8 kakapo and double them
  Predator Free island   remove every rat, stoat, possum and cat (Smite is off)
  Feed 100 people        grow the settlements without losing a native species
  Mast year plague       stop the rat and stoat plague before it reaches the birds
  The rabbit problem     control rabbits without the settlers' stoat "solution"


FOOD WEB (press F, or the Learn tab)
------------------------------------
A live diagram of who eats whom, built from what the simulation records.
Arrows run from food to eater (the way energy flows) and thicken as more is
eaten; white pulses travel along active links and a link flashes when a kill
happens.  Red arrows are introduced predators eating native wildlife.  Circle
size = population; a crossed circle is an extinct species.  Hover or click a
species to see what it gets its energy from and what kills it.  "What's
happening" explains cascades as they happen - e.g. mast year -> rats -> stoats
-> birds.  Switch between the last year of life and all time.


CLASS REPORT (press R, or the Learn tab)
---------------------------------------
Type your name, class and observations, then "Export PDF + CSV".  A folder is
created in "NZ EcoSim reports" next to the program with:
  - a printable PDF: lesson result, key statistics, your observations,
    lifecycle and population charts, pie charts, the food web, extinctions and
    their causes, what you changed, a timeline of events and questions to
    think about
  - population_history.csv, events.csv, deaths.csv, food_web.csv and
    my_actions.csv for spreadsheets


ZOOM, SELECT & FOLLOW
---------------------
  Mouse wheel        zoom in / out at the cursor - zoom out to see the whole
                     island surrounded by ocean (Z resets)
  Drag the map       with Inspect (or the microscope), click-and-drag to move
                     the map; right-drag or WASD / arrow keys also pan;
                     click the minimap to jump
  Click (Inspect)    a person, animal or house to open its info card:
                       - what it is doing right now and WHY (e.g. "Awake at
                         night: the clan is at war, so warriors keep watch and
                         raid while enemies sleep")
                       - for people: their clan, its status (at war / tense /
                         at peace with each neighbour), food, houses, fields
                       - a line shows what they're targeting (red = war)
                       - clicking a house selects the whole clan: its
                         territory, warriors' targets and war fronts
  Follow             keeps the camera on the selected person or animal


PEOPLE & CLANS PANEL (press C, or the "People" button)
-------------------------------------------------------
Clan and job pie charts, a map of where every clan has built (red lines =
wars), and for each clan: what they're doing and why, jobs, food, relations
with every other clan (with a tension bar), and a history of wars and peace.


OCEAN
-----
The sea has plankton, fish and shellfish beds.  Fur seals (kekeno) and little
penguins (korora) eat fish; coastal clans fish and gather shellfish.
Overfishing empties the coast, and mud washed off cleared land smothers the
shellfish.  Draw a Fence sanctuary over the sea to make a marine reserve.
View 8 (Ocean) shows fish stocks.


EXTINCTION
----------
On an island, extinction is forever for flightless species (kiwi, kakapo,
weta, takahe): they only come back if you reintroduce them.  Birds that fly and
sea creatures may recolonise from other islands - an alert explains when.


ADDING LIFE
-----------
Click a species button in the "Add life" tab on the right, then click the map.
Hold Shift to release a group.  Plants are painted with the brush.

  Native animals      Weta, Kiwi, Kakapo, Tui, Kereru, Ruru (morepork), Karearea (falcon),
                      Takahe (South), Kekeno (fur seal), Korora (little penguin)
  Introduced animals  Ship rat, Possum, Stoat, Feral cat, Red deer, Rabbit
  People              Humans - see below
  Native plants       Tussock, Harakeke (flax), Raupo, Manuka, Ponga, Kowhai, Rimu,
                      Kauri (North) or Tawhai / beech (South)
  Introduced plants   Gorse, Wilding pine
  Soil life           Fungi, Microbes

Hover over any species button for a short description.  "+ Design a species"
lets you invent your own, native or introduced.


SETTINGS (button next to New and Pause)
---------------------------------------
  Colour theme   Dark, Light, Ocean, Forest, High contrast + accent colour
  Layout         control panel left or right; charts & alerts bar above or below
  Window         fit screen, original size, or fullscreen
  Day / night    darken the map at night, show a sun & moon icon only, or hide
                 day/night entirely (the last two also stop lightning flashes,
                 for photosensitive viewers)


ECOSYSTEM HEALTH (click the vitality bar)
-----------------------------------------
Opens a drawer with the lifecycle chart (native animals, introduced animals,
people, forest, vitality) and a pie chart of what is pulling vitality down.


ECOLOGICAL HISTORY (History button or Y)
----------------------------------------
A timeline of major events: first people, first house and fields, first voyage,
every war, every new species, every extinction, recoveries, conservation
milestones (first traps, sanctuaries, marine reserves) and more.  Click an
event to see where it happened.


ECOLOGICAL COLLAPSE
-------------------
If the native wildlife is wiped out and cannot recover, a collapse report
appears: the lifecycle chart with its stages (untouched -> people & new
species -> decline -> collapse), every extinction in order with its main
cause, a pie of what killed the native wildlife, key statistics, and what
might have helped.  You can start a new island or keep watching.


HUMANS
------
Click the map with Humans selected to land a group of settlers (fictional
tribes with made-up names).  People are not ordinary animals:
  - they share food and wood as a tribe, build houses and clear fields
  - they hunt (flightless birds that never learned to fear people are easy prey),
    gather, chop trees, burn forest to open land and drain wetlands
  - big tribes split off new settlements; close, hungry tribes go to war and raid
    each other's houses
  - they choose where to settle: near fresh water, the coast (fish), forest
    (timber), flat fertile land - and not too close to other clans.  Houses
    cluster in the village centre with fields around them.
  - wellbeing: clans and people feel stress from war, hunger, worry about
    winter supplies, overcrowding and grief.  Stressed clans stop growing,
    grow hostile, and families leave to start new settlements.
  - scarcity breeds aggression: hungry clans fight over land and food, and
    their raids steal food from the enemy's stores.
  - once a settlement reaches about 12 people on the coast, it sends SHIPS off
    the island to fetch species that "solve" its problems: cats for rats,
    stoats for rabbits, rabbits or deer when game runs out, gorse for hedges,
    pines for timber, possums for a fur trade.  Ships can carry stowaway
    rats.  The Biosecurity slider makes voyages and stowaways rarer.
  - animals flee from people (except naive native birds), and farms and houses
    replace habitat.  Exhausted fields lead to famine and more clearing.


HELPING THE ECOSYSTEM
---------------------
  Trap    pest traps catch rats, stoats, cats, possums and rabbits nearby
  Fence   draw a predator-proof sanctuary: introduced animals can't get in,
          people won't hunt or build inside (click inside one to erase)
  Plant natives, add compost, summon rain, or cull pests with Smite.


ALERTS
------
When something important happens - a species halves, goes extinct, a pest
spreads, a mast year starts, forest is lost, wildfire, drought, erosion,
wetlands drained, famine or war - an alert appears.  Click it (top banner,
the right panel, or the Alerts list at the bottom) to see:
  What's happening  /  Why (from what the simulation recorded)
  How you can help (buttons pick the right tool or species)
  In the real Aotearoa (a related real-world fact)


VIEWS & CHARTS
--------------
  1-8        normal, moisture, nutrients, microbes, fungi, temperature, detritus, ocean
             (hover a view button to see exactly what it shows; a colour key
             appears on the map while a view is active)
  Trends     population history graph (bottom left)
  Pies       pie charts of the fauna, land cover and clans; press P or "Expand"
             for a big version with native vs introduced shares and the ocean
  M          microscope lens to see bacteria and fungal threads


CONTROLS
--------
Space pause   H help   I inspect   M microscope   P pie charts   C clans   N new island
L lessons   F food web   R class report   Y history
Wheel zoom   right-drag/WASD pan   Z reset zoom   Esc deselect
[ ] or Ctrl+wheel  brush size   + / -  time speed   F5 / F9 save / load   F12 screenshot


IT'S ALIVE
----------
The island is saved when you close the window (and every 2 minutes) and keeps
living while you're away - about one simulated day per real hour, up to four
days - with a "Welcome back" report of what happened.


FILES
-----
nz_ecosim.py   the app (window, controls, drawing, alert windows, charts)
world.py       the simulation: terrain, weather, water, plants, animals
species_nz.py  native and introduced species with descriptions
humans.py      tribes, settlements, farming, hunting, war, introductions
alerts.py      ecological alerts and their explanations
views.py       new-island generator, people & clans panel, behaviour text
scenarios.py   lessons: setups, goals and real-world stories
lessons_ui.py  lesson picker, lesson result and the on-map goal tracker
foodweb.py     the live food web
report.py      class report export (PDF + CSV)
webplatform.py browser support (saving, downloads) for the web version
live_runner.py advances the locked live island on the website
web/           the website pages (live viewer, in-browser player)
tools/         build_site.py assembles the website
.github/       the GitHub Actions schedule that runs the live island
ui_kit.py      buttons, sliders, pie charts
config.py      shared settings and calendar

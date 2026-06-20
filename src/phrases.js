// danskLearn shared phrase bank — used by dansktale.html and danskhor.html.
//
// Stable IDs (e.g. "food-12") survive reorderings so spaced-repetition state in
// localStorage doesn't drift as we add or remove phrases.
//
// When the standalone files load this directly, window.DanskPhrases.BANK is
// the source of truth. When build.py assembles index.html, this file is
// inlined once at the top of the bundled scripts.

window.DanskPhrases = {
  BANK: [
    // Greetings (12)
    {id:"greet-1",  da:"Hej",                          en:"Hi",                                 cat:"Greetings"},
    {id:"greet-2",  da:"Hej hej",                      en:"Bye",                                cat:"Greetings"},
    {id:"greet-3",  da:"God morgen",                   en:"Good morning",                       cat:"Greetings"},
    {id:"greet-4",  da:"God aften",                    en:"Good evening",                       cat:"Greetings"},
    {id:"greet-5",  da:"God nat",                      en:"Good night",                         cat:"Greetings"},
    {id:"greet-6",  da:"Hvordan har du det?",          en:"How are you?",                       cat:"Greetings"},
    {id:"greet-7",  da:"Jeg har det godt, tak",        en:"I'm well, thanks",                   cat:"Greetings"},
    {id:"greet-8",  da:"Tak",                          en:"Thanks",                             cat:"Greetings"},
    {id:"greet-9",  da:"Tusind tak",                   en:"Thank you very much",                cat:"Greetings"},
    {id:"greet-10", da:"Velbekomme",                   en:"You're welcome",                     cat:"Greetings"},
    {id:"greet-11", da:"Vi ses senere",                en:"See you later",                      cat:"Greetings"},
    {id:"greet-12", da:"Undskyld",                     en:"Excuse me / Sorry",                  cat:"Greetings"},

    // Daily Life (18)
    {id:"daily-1",  da:"Jeg står op klokken syv",      en:"I get up at seven o'clock",          cat:"Daily Life"},
    {id:"daily-2",  da:"Jeg laver morgenmad",          en:"I make breakfast",                   cat:"Daily Life"},
    {id:"daily-3",  da:"Hvor er nøglerne?",            en:"Where are the keys?",                cat:"Daily Life"},
    {id:"daily-4",  da:"Jeg cykler på arbejde",        en:"I cycle to work",                    cat:"Daily Life"},
    {id:"daily-5",  da:"Jeg taler i telefon",          en:"I'm on the phone",                   cat:"Daily Life"},
    {id:"daily-6",  da:"Vi spiser middag sammen",      en:"We eat dinner together",             cat:"Daily Life"},
    {id:"daily-7",  da:"Hunden skal luftes",           en:"The dog needs to be walked",         cat:"Daily Life"},
    {id:"daily-8",  da:"Jeg vasker tøj",               en:"I'm doing laundry",                  cat:"Daily Life"},
    {id:"daily-9",  da:"Vi handler ind om lørdagen",   en:"We do groceries on Saturdays",       cat:"Daily Life"},
    {id:"daily-10", da:"Jeg ser nyhederne",            en:"I'm watching the news",              cat:"Daily Life"},
    {id:"daily-11", da:"Jeg går i seng nu",            en:"I'm going to bed now",               cat:"Daily Life"},
    {id:"daily-12", da:"Hvor bor du?",                 en:"Where do you live?",                 cat:"Daily Life"},
    {id:"daily-13", da:"Jeg bor i København",          en:"I live in Copenhagen",               cat:"Daily Life"},
    {id:"daily-14", da:"Hvad arbejder du med?",        en:"What do you do for work?",           cat:"Daily Life"},
    {id:"daily-15", da:"Jeg er studerende",            en:"I'm a student",                      cat:"Daily Life"},
    {id:"daily-16", da:"Hvor gammel er du?",           en:"How old are you?",                   cat:"Daily Life"},
    {id:"daily-17", da:"Hvad hedder du?",              en:"What's your name?",                  cat:"Daily Life"},
    {id:"daily-18", da:"Jeg hedder Anna",              en:"My name is Anna",                    cat:"Daily Life"},

    // Food (14)
    {id:"food-1",   da:"Et glas vand, tak",            en:"A glass of water, please",           cat:"Food"},
    {id:"food-2",   da:"Hvad anbefaler du?",           en:"What do you recommend?",             cat:"Food"},
    {id:"food-3",   da:"Jeg vil gerne bestille",       en:"I'd like to order",                  cat:"Food"},
    {id:"food-4",   da:"Smager det godt?",             en:"Does it taste good?",                cat:"Food"},
    {id:"food-5",   da:"Det smager dejligt",           en:"It tastes lovely",                   cat:"Food"},
    {id:"food-6",   da:"Jeg er sulten",                en:"I'm hungry",                         cat:"Food"},
    {id:"food-7",   da:"Jeg er tørstig",               en:"I'm thirsty",                        cat:"Food"},
    {id:"food-8",   da:"Må jeg få regningen?",         en:"May I have the bill?",               cat:"Food"},
    {id:"food-9",   da:"Hvor er menuen?",              en:"Where is the menu?",                 cat:"Food"},
    {id:"food-10",  da:"En kop kaffe, tak",            en:"A cup of coffee, please",            cat:"Food"},
    {id:"food-11",  da:"Jeg er vegetar",               en:"I'm a vegetarian",                   cat:"Food"},
    {id:"food-12",  da:"Det var lækkert",              en:"That was delicious",                 cat:"Food"},
    {id:"food-13",  da:"Hvad indeholder retten?",      en:"What's in the dish?",                cat:"Food"},
    {id:"food-14",  da:"Jeg er allergisk over for nødder", en:"I'm allergic to nuts",           cat:"Food"},

    // Travel (14)
    {id:"travel-1", da:"Hvor er stationen?",           en:"Where is the station?",              cat:"Travel"},
    {id:"travel-2", da:"En billet til Aarhus, tak",    en:"One ticket to Aarhus, please",       cat:"Travel"},
    {id:"travel-3", da:"Hvornår kører toget?",         en:"When does the train leave?",         cat:"Travel"},
    {id:"travel-4", da:"Hvor lang tid tager det?",     en:"How long does it take?",             cat:"Travel"},
    {id:"travel-5", da:"Jeg har mistet min taske",     en:"I've lost my bag",                   cat:"Travel"},
    {id:"travel-6", da:"Hvor er toilettet?",           en:"Where is the toilet?",               cat:"Travel"},
    {id:"travel-7", da:"Kan du hjælpe mig?",           en:"Can you help me?",                   cat:"Travel"},
    {id:"travel-8", da:"Jeg er turist",                en:"I'm a tourist",                      cat:"Travel"},
    {id:"travel-9", da:"Hvor meget koster det?",       en:"How much does it cost?",             cat:"Travel"},
    {id:"travel-10",da:"Jeg leder efter et hotel",     en:"I'm looking for a hotel",            cat:"Travel"},
    {id:"travel-11",da:"Til venstre eller til højre?", en:"Left or right?",                     cat:"Travel"},
    {id:"travel-12",da:"Lige ud",                      en:"Straight ahead",                     cat:"Travel"},
    {id:"travel-13",da:"Er det langt herfra?",         en:"Is it far from here?",               cat:"Travel"},
    {id:"travel-14",da:"Hvilken bus skal jeg tage?",   en:"Which bus should I take?",           cat:"Travel"},

    // Numbers/Time (10)
    {id:"num-1",    da:"Hvad er klokken?",             en:"What time is it?",                   cat:"Numbers/Time"},
    {id:"num-2",    da:"Klokken er to",                en:"It's two o'clock",                   cat:"Numbers/Time"},
    {id:"num-3",    da:"Klokken er kvart over to",     en:"It's quarter past two",              cat:"Numbers/Time"},
    {id:"num-4",    da:"Klokken er halv tre",          en:"It's half past two",                 cat:"Numbers/Time"},
    {id:"num-5",    da:"Det koster halvtreds kroner",  en:"It costs fifty kroner",              cat:"Numbers/Time"},
    {id:"num-6",    da:"I morgen tidlig",              en:"Tomorrow morning",                   cat:"Numbers/Time"},
    {id:"num-7",    da:"I aften",                      en:"Tonight",                            cat:"Numbers/Time"},
    {id:"num-8",    da:"I weekenden",                  en:"On the weekend",                     cat:"Numbers/Time"},
    {id:"num-9",    da:"Hver dag",                     en:"Every day",                          cat:"Numbers/Time"},
    {id:"num-10",   da:"Sidste år",                    en:"Last year",                          cat:"Numbers/Time"},

    // Feelings (12)
    {id:"feel-1",   da:"Jeg er træt",                  en:"I'm tired",                          cat:"Feelings"},
    {id:"feel-2",   da:"Jeg er glad",                  en:"I'm happy",                          cat:"Feelings"},
    {id:"feel-3",   da:"Jeg er ked af det",            en:"I'm sad",                            cat:"Feelings"},
    {id:"feel-4",   da:"Jeg savner dig",               en:"I miss you",                         cat:"Feelings"},
    {id:"feel-5",   da:"Det var hyggeligt",            en:"That was lovely / cozy",             cat:"Feelings"},
    {id:"feel-6",   da:"Jeg keder mig",                en:"I'm bored",                          cat:"Feelings"},
    {id:"feel-7",   da:"Jeg er forvirret",             en:"I'm confused",                       cat:"Feelings"},
    {id:"feel-8",   da:"Jeg er forelsket",             en:"I'm in love",                        cat:"Feelings"},
    {id:"feel-9",   da:"Jeg er stolt af dig",          en:"I'm proud of you",                   cat:"Feelings"},
    {id:"feel-10",  da:"Det er pinligt",               en:"That's embarrassing",                cat:"Feelings"},
    {id:"feel-11",  da:"Jeg er nervøs",                en:"I'm nervous",                        cat:"Feelings"},
    {id:"feel-12",  da:"Det er irriterende",           en:"That's annoying",                    cat:"Feelings"},
  ],
};

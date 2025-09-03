import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Database setup
DATABASE = 'ChibiBytes_users.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Enable dictionary-style access
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Create watchlist table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                anime_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                year TEXT,
                rating TEXT,
                image TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Create anime table
        cursor.execute('''
                    CREATE TABLE IF NOT EXISTS anime (
                        id INTEGER PRIMARY KEY,
                        title TEXT NOT NULL,
                        year TEXT,
                        rating TEXT,
                        image TEXT NOT NULL,
                        modalImage TEXT NOT NULL,
                        category TEXT NOT NULL,
                        description TEXT NOT NULL,
                        insights TEXT NOT NULL
                    )
                ''')




        # Create movie table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                year TEXT,
                rating TEXT,
                image TEXT NOT NULL,
                modalImage TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                insights TEXT NOT NULL,
                director TEXT NOT NULL,
                duration TEXT NOT NULL
            )
        ''')
        db.commit()

        # Populate anime table if empty
        cursor.execute("SELECT COUNT(*) FROM anime")
        if cursor.fetchone()[0] == 0:
            # This is a simplified example - you'd need to insert all 75 anime entries
            anime_data = [
                {
                    "id": 1,
                    "title": "One Piece",
                    "year": "1999",
                    "rating": "8.75",
                    "image": "https://i.pinimg.com/736x/65/e9/a6/65e9a662394181e7ac4632cf202c2671.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/89/13/be/8913be5f2ffacb07c34168c4abc776c0.jpg",
                    "category": "Popular,Adventure,Fantasy,Action,Shonen",
                    "description": "Monkey D. Luffy sets out to become the King of the Pirates by finding the legendary treasure known as One Piece.",
                    "insights": "One Piece is a monumental saga known for its rich world-building, emotionally charged arcs, and decades-spanning character development. With over 1000 episodes, it balances humor, action, and powerful storytelling, creating a legacy that has redefined long-running anime and continues to attract new generations of fans."
                },
                {
                    "id": 2,
                    "title": "Bleach",
                    "year": "2004",
                    "rating": "8.2",
                    "image": "https://i.pinimg.com/1200x/64/68/f4/6468f4516814b2bd80aca8477f017b1f.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/40/d4/19/40d4197c896425fbf04be9df708747d5.jpg",
                    "category": "Action, Supernatural, Shonen, Popular",
                    "description": "Ichigo Kurosaki becomes a Soul Reaper to protect the living from evil spirits and guide the dead to the afterlife, uncovering a dark and dangerous world.",
                    "insights": "Bleach captivates with its dynamic blend of soul‑reaping action and intricate world‑building. The series weaves together the human and spirit realms through kinetic swordplay, creative use of zanpakutō abilities, and escalating threats that constantly raise the stakes. Beyond its thrilling battles, Bleach shines in its exploration of duty, friendship, and personal sacrifice, as Ichigo and his allies confront moral dilemmas and uncover layers of conspiracy. With a sprawling cast whose growth mirrors the series’ tonal shifts—from lighthearted adventures to epic climaxes—it remains a milestone in long‑form shōnen storytelling."
                },
                {
                    "id": 3,
                    "title": "Jujutsu Kaisen",
                    "year": "2020",
                    "rating": "8.6",
                    "image": "https://i.pinimg.com/736x/b4/48/c2/b448c215859a528035f64b10d992d968.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/9b/38/0e/9b380e1eb89577504cef7d4d61768904.jpg",
                    "category": "Popular, Top, New, Shonen, Action, Supernatural",
                    "description": "A boy swallows a cursed talisman and becomes entangled in the world of sorcerers and curses.",
                    "insights": "Jujutsu Kaisen elevates the modern shōnen genre through its masterful choreography, rich supernatural lore, and balanced emotional beats. Its tightly crafted curse mechanics and layered world rules give meaning to every confrontation, while the series’ dark undertones are offset by moments of humor and warmth among its core group. Protagonist Yuji Itadori’s moral compass drives a narrative that tackles loss, power, and camaraderie, and the fluid animation—particularly in high‑octane sequences—cements Jujutsu Kaisen as a contemporary classic with enduring appeal."
                },
                {
                    "id": 4,
                    "title": "Attack on Titan",
                    "year": "2013",
                    "rating": "9.1",
                    "image": "https://i.pinimg.com/736x/a2/79/39/a27939d25b8ef380bccb0e1128157386.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/17/90/b7/1790b728a393b8d1386b327dd7a17f26.jpg",
                    "category": "Popular, Top, New, Shonen, Action, Supernatural, Drama, Fantasy",
                "description": "Humanity fights for survival against giant humanoid Titans threatening their existence.",
            "insights": "Attack on Titan redefined epic anime drama with its relentless tension, moral complexity, and jaw‑dropping narrative twists. From the visceral horror of Titans’ assaults to the ethical quandaries faced by humanity’s defenders, every arc deepens the stakes. The show excels in portraying flawed characters whose loyalties and beliefs are constantly tested, set against a backdrop of political intrigue and existential dread. Its cinematic direction and haunting score amplify moments of despair and triumph alike, making it both a thought‑provoking allegory and an adrenaline‑charged spectacle that resonates far beyond the genre."
            },

                {
                    "id": 5,
                    "title": "My Hero Academia",
                    "year": "2016",
                    "rating": "8.4",
                    "image": "https://i.pinimg.com/736x/bf/b2/19/bfb219425771bad20ac2e549ea8d7935.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/99/68/40/996840e5b11dfe06e5a664d43298b096.jpg",
                    "category": "Popular, Fantasy, Shonen, Action, Supernatural",
                "description": "A boy without powers in a super-powered world strives to become the greatest hero.",
            "insights": "My Hero Academia breathes fresh life into the superhero paradigm by blending high‑school coming‑of‑age themes with superpowered world-building. Its expansive Quirk system allows for inventive battles, and the genuine mentor‑student dynamics—particularly between All Might and Midoriya—infuse emotional weight into each challenge. Through ensemble storytelling, the series explores diverse character arcs centered on sacrifice, resilience, and the true meaning of heroism. Consistently balancing thrills, humor, and heartfelt moments, My Hero Academia has become a modern shōnen touchstone for its uplifting yet grounded approach."
            },
            {
                "id": 6,
                "title": "Chainsaw Man",
                "year": "2022",
                "rating": "8.7",
                "image": "https://i.pinimg.com/1200x/e3/97/4f/e3974f362b0fa3eaa0cfdcb64a2fef5b.jpg",
                "modalImage": "https://i.pinimg.com/736x/60/7c/fd/607cfdc85e1328d970b8605b3d248b49.jpg",
                "category": "Popular, New, Shonen, Fantasy",
            "description": "A young man gains the ability to transform parts of his body into chainsaws.",
            "insights": "Chainsaw Man shatters expectations with its grotesque yet gleefully visceral aesthetic, blending dark humor with moments of poignant humanity. The series’ unpredictable narrative tosses protagonists between absurd comedy and existential peril, while its inventive devil‑blood mechanics fuel brutal, artful action. At its core is Denji’s raw, uncomplicated desire for connection and purpose, which anchors the story’s surreal violence. Chainsaw Man’s willingness to subvert shōnen conventions—eschewing traditional power‑ups for chaotic evolution—makes it a bold, unforgettable ride that challenges and redefines genre boundaries."
            },
            {
                "id": 7,
                "title": "Solo Leveling",
                "year": "2024",
                "rating": "8.5",
                "image": "https://i.pinimg.com/1200x/7c/a1/97/7ca1971262c9271bd417ade2987ec1e5.jpg",
                "modalImage": "https://i.pinimg.com/736x/5b/35/bd/5b35bd928b72d8d921dec48baffeb558.jpg",
                "category": "Popular, Top, Fantasy, New, Action, Adventure",
            "description": "In a world where hunters battle monsters, a weak hunter gains the ability to level up infinitely.",
            "insights": "Solo Leveling hooks viewers with a streamlined power‑progression premise that emphasizes clear stakes and rewarding growth. Sung Jin‑woo’s evolution from weakest hunter to near‑invincible force is portrayed through visually stunning dungeon raids and boss battles that escalate in scale and creativity. The series balances its action‑driven core with quieter moments of strategy, camaraderie, and self‑reflection, giving depth to its protagonist’s ambition. With crisp animation and a satisfying narrative arc that consistently delivers tension and payoff, Solo Leveling stands out as a definitive modern fantasy adventure."
            },
            {
                "id": 8,
                "title": "Fullmetal Alchemist: Brotherhood",
                "year": "2009",
                "rating": "9.12",
                "image": "https://i.pinimg.com/1200x/fa/49/ab/fa49ab460634173f3fb2cf597585a063.jpg",
                "modalImage": "https://i.pinimg.com/1200x/29/a0/b5/29a0b53b4c0377c3405489b4a025d69d.jpg",
                "category": "Popular, Top, Shonen, Top, Fantasy",
            "description": "Two brothers use alchemy in a quest to restore their bodies after a failed transmutation—uncovering deep government conspiracies along the way.",
            "insights": "Renowned for its flawless pacing and multi‑layered narrative, Fullmetal Alchemist: Brotherhood masterfully explores themes of sacrifice, redemption, and the human condition. With unforgettable characters, pulse‑pounding action, and moments of profound emotional resonance, it offers both philosophical depth and thrilling adventure, earning its place as a landmark series that continues to captivate audiences worldwide."
            },
            {
                "id": 9,
                "title": "Naruto",
                "year": "2002",
                "rating": "8.30",
                "image": "https://i.pinimg.com/736x/05/20/95/05209578d20ec18d4aba21d2508c2a9e.jpg",
                "modalImage": "https://i.pinimg.com/1200x/8d/13/1b/8d131bc6e06e15d21fb97c27f97b8e30.jpg",
                "category": "Popular, Action, Ninja, Shonen, Adventure, Comedy",
            "description": "Naruto Uzumaki, a spirited ninja with dreams of becoming Hokage, struggles to gain recognition while harboring a powerful beast within.",
            "insights": "Naruto blends emotional storytelling with intense ninja battles, focusing on themes of perseverance, friendship, and redemption. With iconic characters and arcs like the Chunin Exams and the Sasuke Retrieval, it’s a cultural milestone that inspired a global generation and set the stage for Naruto: Shippuden and beyond."
            },
            {
                "id": 10,
                "title": "Death Note",
                "year": "2006",
                "rating": "8.63",
                "image": "https://i.pinimg.com/736x/82/90/06/829006f7d871f3039e4ded4e902d19a0.jpg",
                "modalImage": "https://i.pinimg.com/1200x/ae/f4/1d/aef41d5f671f4f5a90cb63c9c6846ebd.jpg",
                "category": "Popular, Thriller, Supernatural, Shonen, Mystery, Psychological, Supernatural",
            "description": "After discovering a notebook that can kill anyone whose name is written in it, genius student Light Yagami sets out to cleanse the world of evil.",
            "insights": "Death Note is a masterclass in psychological tension and moral conflict. Its gripping cat-and-mouse game between Light and L delivers nonstop suspense, challenging viewers to question justice, power, and consequence. With its stylish direction and unforgettable plot twists, it's one of the most influential anime thrillers ever made."
            },
            {
                "id": 11,
                "title": "Frieren: Beyond Journey’s End",
                "year": "2023",
                "rating": "9.35",
                "image": "https://i.pinimg.com/736x/ae/b8/1e/aeb81e901a22cd9b814671e1a4007c79.jpg",
                "modalImage": "https://i.pinimg.com/1200x/3f/ea/a8/3feaa8550def439cd6c58c869308a986.jpg",
                "category": "Popular, Top, New, Slice‑of‑life, Shonen, Fantasy",
            "description": "An elven mage named Frieren reflects on her century‑long journey after her hero party disbands, rediscovering meaning and forging new bonds.",
            "insights": "Frieren shines through its contemplative pacing and emotional maturity. It explores themes of mortality, memory, and the value of time, all while delivering beautifully understated magic and heartfelt character moments. Its unique blend of reflective storytelling and gentle adventure resonates deeply with both longtime fantasy fans and viewers seeking a more introspective journey."
            },
            {
                "id": 12,
                "title": "Dandadan",
                "year": "2024",
                "rating": "8.84",
                "image": "https://i.pinimg.com/1200x/eb/9e/71/eb9e711d53bf9dc74f32e9ec2d5bcfed.jpg",
                "modalImage": "https://i.pinimg.com/736x/dc/56/56/dc5656366261d648accec1d7501b66c2.jpg",
                "category": "Popular, New, Comedy, Fantasy, Horror",
            "description": "When ghost‑obsessed Momo and alien‑believing Okarun team up, they uncover startling supernatural and extraterrestrial mysteries.",
            "insights": "Dandadan blends horror, sci‑fi, and slapstick with breath‑taking animation in a fresh, unpredictable mix. Its rapid‑fire humor and creative monster designs keep viewers engaged, while the chemistry between the leads adds heart and laughs. This genre‑bending series has earned praise for its bold tone shifts and standout visual flair."
            },
            {
                "id": 13,
                "title": "Blue Lock",
                "year": "2022",
                "rating": "8.75",
                "image": "https://i.pinimg.com/1200x/4e/5b/43/4e5b43882d323a81573c88c47ba98875.jpg",
                "modalImage": "https://i.pinimg.com/1200x/26/9e/30/269e30666955c8f11080654be16d29de.jpg",
                "category": "Popular, New, Psychological, Sports, Shonen",
            "description": "Strikers from across Japan are locked in a brutal training camp designed to create the world’s greatest egoistic striker.",
            "insights": "Blue Lock is a psychological sports anime that thrusts viewers into an intense, high-stakes environment. Its focus on individual ambition, ego clashes, and cutthroat competition in soccer offers a fresh, adrenaline-fueled take on the genre. With dynamic matches and compelling character arcs, it challenges the notion of teamwork and shines a light on personal ambition."
            },

            {
                "id": 14,
                "title": "Kaiju No.8",
                "year": "2024",
                "rating": "8.55",
                "image": "https://i.pinimg.com/736x/e7/9e/7e/e79e7e3caf043183a40f0e7413ddd516.jpg",
                "modalImage": "https://i.pinimg.com/736x/2b/40/b1/2b40b1920a17abc833cb2b6aa7e94a15.jpg",
                "category": "Popular, New, Shonen, Fantasy",
            "description": "A cleanup crew member for a kaiju defense force unexpectedly transforms into Kaiju No. 8 while still retaining his human mind.",
            "insights": "Kaiju No.8 mixes monster‑bashing action with a heartfelt coming‑of‑age story. Its unique premise—balancing the chaos of kaiju destruction with the protagonist’s internal struggle—brings emotional weight to epic battles. Sharp animation and strong character design elevate the drama, making it a standout in modern shounen."
            },
            {
                "id": 15,
                "title": "My Happy Marriage",
                "year": "2023",
                "rating": "8.40",
                "image": "https://i.pinimg.com/1200x/4b/62/92/4b62922f99d1163a5539648e9175549f.jpg",
                "modalImage": "https://i.pinimg.com/1200x/28/9c/81/289c8190d9de55dfc2d5c29fa7b81fc9.jpg",
                "category": "Popular, New, Historical, Fantasy, Romance",
            "description": "In an alternate early–20th‑century Japan, an arranged marriage forces Miyo to confront her insecurities and honor through love and personal growth.",
            "insights": "My Happy Marriage captivates with its tender emotional resonance and period romance setting. The slow‑burn relationship between Miyo and Kiyoka is grounded in nuanced character development, exploring self‑worth, duty, and healing. Beautifully animated and thoughtfully paced, it offers satisfying drama without overwhelming melodrama."
            },
            {
                "id": 16,
                "title": "Wind Breaker",
                "year": "2024",
                "rating": "7.95",
                "image": "https://i.pinimg.com/1200x/66/cd/86/66cd86b77f1916fabb9a4e3f1efcb064.jpg",
                "modalImage": "https://i.pinimg.com/736x/92/e7/e0/92e7e02328b32b06e3260317dca54049.jpg",
                "category": "New, Martial arts, School, Shonen, Action",
            "description": "Delinquent Haruka Sakura transfers to Furin High, a school run by brawling gangs, and fights to become their top protector while forging meaningful bonds.",
            "insights": "Wind Breaker delivers high‑octane fight choreography with slick CloverWorks animation and dynamic camera work. It stands out by blending intense hand‑to‑hand combat with emotional growth—Sakura’s journey from isolation to trust feels earned. Though some find the pacing uneven, fans praise its strong character arcs, soundtrack, and vibrant visuals."
            },
            {
                "id": 17,
                "title": "Steins;Gate",
                "year": "2011",
                "rating": "9.08",
                "image": "https://i.pinimg.com/736x/41/b6/65/41b665a206b1d02f074d79c03d70fa50.jpg",
                "modalImage": "https://i.pinimg.com/1200x/3e/a4/f3/3ea4f3ff8d45616e224e2b324bba4603.jpg",
                "category": "Mystery, Sci-Fi, Thriller, Top, Psychological, Time travel",
            "description": "A self-proclaimed mad scientist and his friends accidentally discover time travel via a modified microwave and must navigate the consequences of altering the past.",
            "insights": "Steins;Gate is a phenomenal blend of suspense, emotional depth, and science fiction. Its intricate time-travel mechanics, unforgettable character arcs—especially Rintarou and Kurisu—and escalating tension culminate in a deeply satisfying, heartbreaking payoff. It’s widely regarded as one of the most meticulously written anime, praised for balancing intellectual puzzles with profound human emotion."
            },
            {
                "id": 18,
                "title": "Hunter × Hunter (2011)",
                "year": "2011",
                "rating": "9.04",
                "image": "https://i.pinimg.com/736x/62/25/a9/6225a9908ad08fd6d0b3929dd99d8a95.jpg",
                "modalImage": "https://i.pinimg.com/1200x/d8/7f/bc/d87fbc237490c030c061da43418b5b61.jpg",
                "category": "Popular, Top, Psychological, Adventure, Action, Fantasy, Shonen",
            "description": "Gon Freecss embarks on a journey to become a Hunter like his father, meeting friends and confronting dark forces as he learns the art of Nen.",
            "insights": "Hunter × Hunter (2011) is celebrated for its exceptional world‑building, evolving character arcs, and inventive Nen system. From the hopeful Hunter Exam to the high‑stakes Chimera Ant saga, it masterfully shifts tone and intensity. Fans and critics alike hail its narrative depth, moral complexity, and powerful emotional beats, solidifying its status as a modern shounen classic."
            },
            {
                "id": 19,
                "title": "Oshi no Ko",
                "year": "2023",
                "rating": "8.65",
                "image": "https://i.pinimg.com/1200x/02/a6/d0/02a6d011f118199e30f9e0411cebb83b.jpg",
                "modalImage": "https://i.pinimg.com/736x/d4/51/9b/d4519b14f475f9811fae0888784485d0.jpg",
                "category": "Top, New, Idol, Mystery, Psychological, Mystery, Supernatural",
            "description": "A doctor is reincarnated as the secret child of a popular idol, navigating the dark underbelly of the entertainment world while seeking to uncover the truth behind tragic events.",
            "insights": "Oshi no Ko blends emotional drama, celebrity culture critique, and supernatural twists in a bold and unpredictable narrative. Its compelling mystery, layered characters, and haunting atmosphere strike a rare balance between heartfelt vulnerability and industry satire, making it a standout psychological drama in recent anime."
            },
            {
                "id": 20,
                "title": "Cowboy Bebop",
                "year": "1998",
                "rating": "8.80",
                "image": "https://i.pinimg.com/736x/21/9f/6f/219f6f65cc3e05a681eb4c3d765508c0.jpg",
                "modalImage": "https://i.pinimg.com/1200x/cd/2d/19/cd2d19595b0117aa3aad19df762c28f1.jpg",
                "category": "Top, Sci‑fi, Neo‑noir, Space, Comedy, Action, Adventure",
            "description": "A ragtag crew of bounty hunters aboard the spaceship Bebop travel the galaxy chasing criminals while confronting their pasts.",
            "insights": "Cowboy Bebop fuses jazz‑infused noir atmosphere with stylish sci‑fi action and deeply flawed characters. Each episodic tale blends existential themes and emotional introspection, anchored by Spike Spiegel’s cool detachment and inner turmoil. Its groundbreaking soundtrack, visual storytelling, and mature tone make it a timeless classic that transcends genres."
            },
            {
                "id": 21,
                "title": "Spy × Family",
                "year": "2022",
                "rating": "8.30",
                "image": "https://i.pinimg.com/736x/d6/ed/3c/d6ed3c16346f2a355e20f06e1f89e692.jpg",
                "modalImage": "https://i.pinimg.com/1200x/6b/3c/10/6b3c10bca89db58fd1d529d88b8ac071.jpg",
                "category": "New, Popular, Slice-of-life, Spy, Family, Comedy",
            "description": "A spy must build a fake family to execute a mission, only to discover his new wife is an assassin and his adopted daughter is a telepath.",
            "insights": "Bright, witty, and heartwarming, Spy × Family masterfully balances espionage thrills with family comedy. The chemistry between Loid, Yor, and Anya delivers both action and adorable slice‑of‑life moments. With clever humor, emotional beats, and stylish animation, it’s a feel‑good hit that resonates across audiences."
            },
            {
                "id": 22,
                "title": "One Punch Man",
                "year": "2015",
                "rating": "8.55",
                "image": "https://i.pinimg.com/1200x/d4/21/9b/d4219b37f27c6ac7cd5ab5539a63abff.jpg",
                "modalImage": "https://i.pinimg.com/1200x/1c/14/ad/1c14ad947ddd099d1d64ef6ddf0d0b5b.jpg",
                "category": "Popular, Superhero, Parody, Shonen, Action, Comedy, Sci-Fi",
            "description": "Saitama, a hero so powerful that he defeats any opponent with a single punch, struggles with the boredom of being unbeatable while forming bonds with quirky allies.",
            "insights": "One Punch Man hilariously subverts superhero tropes with its deadpan humor and overpowered protagonist, while delivering breathtaking animation in its action sequences. Beneath the comedy, it explores themes of purpose, motivation, and the quest for meaning when limits are removed. Its blend of satire and spectacle has made it a modern anime icon."
            },
            {
                "id": 23,
                "title": "Dr. Stone",
                "year": "2019",
                "rating": "9.20",
                "image": "https://i.pinimg.com/1200x/63/5d/ea/635deaaed5b52dc5a328782a03bedc10.jpg",
                "modalImage": "https://i.pinimg.com/1200x/38/44/3f/38443fc663612aaf1fa86329f5278744.jpg",
                "category": "Popular, Adventure, Post‑apocalyptic, Shonen, Comedy",
            "description": "Thousands of years after humanity is turned to stone, genius Senku Ishigami awakens and aims to rebuild civilization using science.",
            "insights": "Dr. Stone excels by merging real science with adventure in a post‑apocalyptic world. It builds tension and wonder through inventive engineering feats, insightful character bonds, and steady pacing. Despite occasional animation limitations in later seasons, its charm lies in celebrating curiosity, teamwork, and human ingenuity—making it a standout for sci‑fi fans. (~80 words)"
            },
            {
                "id": 24,
                "title": "Berserk",
                "year": "1997",
                "rating": "8.2",
                "image": "https://i.pinimg.com/1200x/18/a7/fa/18a7fa614effbbbc8717e1e9627a86ac.jpg",
                "modalImage": "https://i.pinimg.com/736x/5d/2e/62/5d2e625e0a4d08133a44400c4de738c9.jpg",
                "category": "Fantasy, Horror, Seinen",
            "description": "Guts, a lone mercenary wielding the massive Dragonslayer blade, battles demons and betrayal in a brutal medieval world, driven by revenge and survival.",
            "insights": "Berserk captivates with its profoundly dark and mature storytelling, exploring themes like fate, trauma, and the human will. Guts’ character arc—from rage‑driven mercenary to introspective survivor—paired with Susumu Hirasawa’s haunting soundtrack, creates an atmospheric masterpiece. Though the animation may feel dated or uneven, its emotional resonance, philosophical depth, and brutal beauty continue to deeply impact viewers. (<100 words)"
            },
            {
                "id": 25,
                "title": "Demon Slayer: Kimetsu no Yaiba",
                "year": "2019",
                "rating": "8.65",
                "image": "https://i.pinimg.com/736x/2a/fb/c7/2afbc7330c27de1174d243bdff245302.jpg",
                "modalImage": "https://i.pinimg.com/736x/db/67/75/db6775199812a55a3e46cf59b29d025c.jpg",
                "category": "Popular, Adventure, Fantasy, Supernatural, Shonen",
            "description": "After his family is slaughtered and his sister Nezuko turned into a demon, Tanjiro joins the Demon Slayer Corps to avenge his loved ones and find a cure.",
            "insights": "Demon Slayer stands out for its stunning ufotable animation, intense sword-fighting choreography, and emotional depth. It blends gut-wrenching drama, familial themes, and breathtaking visuals into a cohesive whole. It’s the highest-grossing Japanese anime franchise, with multiple award wins—including Best Continuing Series and Best Animation at the Crunchyroll Anime Awards—and continues its finale with a major film trilogy beginning July 18, 2025."
            },
            {
                "id": 26,
                "title": "Black Clover",
                "year": "2017",
                "rating": "8.10",
                "image": "https://i.pinimg.com/736x/27/dd/a6/27dda6bb9b3f27ebf2ee9bd5dd9ac6cd.jpg",
                "modalImage": "https://i.pinimg.com/736x/d9/f9/e8/d9f9e8b99826c53ff7263e453c890825.jpg",
                "category": "Action, Magic, Shonen, Fantasy, Adventure",
            "description": "Asta and Yuno, orphans raised together, aspire to become Wizard King in a world where magic defines status—Asta despite being born without magic harnesses anti-magic abilities.",
            "insights": "Black Clover delivers high-energy magic action grounded in resilience and friendship. Asta’s journey from underdog to anti-magic powerhouse drives the narrative, while the dynamic camaraderie of the Black Bulls and escalating threats build momentum. The long-running 170-episode series also spawned the film *Sword of the Wizard King* (2023) and has now been officially confirmed to return with a sequel season in production—celebrating its 10th anniversary and continuing its climb toward Wizard King status."
            },
            {
                "id": 27,
                "title": "Re:Zero - Starting Life in Another World",
                "year": "2016",
                "rating": "8.23",
                "image": "https://i.pinimg.com/736x/1f/02/5e/1f025ed094bd6e156df9589f4c3b80fe.jpg",
                "modalImage": "https://i.pinimg.com/1200x/31/4e/9a/314e9a89ae515e47879bcb8198ccfa76.jpg",
                "category": "Isekai, Time travel, Fantasy, Drama, Psychological",
            "description": "Subaru Natsuki is transported to a fantasy world where he discovers he can rewind time by dying, and he must repeatedly face death to protect those he loves.",
            "insights": "Re:Zero is a gripping isekai that subverts genre norms through its dark time‑loop mechanic and flawed protagonist. Subaru’s repeated deaths force him to confront moral dilemmas and trauma, alongside complex characters and emotional stakes. The season 3 premiere scored an impressive **8.96**, making it the top-rated isekai on MyAnimeList in late 2024 :contentReference[oaicite:0]{index=0}."
            },
            {
                "id": 28,
                "title": "Overlord",
                "year": "2015",
                "rating": "8.2",
                "image": "https://i.pinimg.com/736x/ee/3f/dd/ee3fdd307fe6cc81c5aabf4ada540810.jpg",
                "modalImage": "https://i.pinimg.com/736x/e4/18/d6/e418d61c9b90aa086e6a020572167eae.jpg",
                "category": "Isekai, Dark fantasy, Fantasy, Action",
            "description": "When the VRMMORPG Yggdrasil shuts down, the powerful skeletal overlord Momonga remains logged in—and wakes up in a new, real world that resembles the game.",
            "insights": "Overlord stands out by centering on an antihero whose rise to power is both strategic and morally complex. Balancing intense dark‑fantasy battles with political intrigue and character loyalty, it meticulously builds Ains Ooal Gown's empire. The series earned strong fan ratings (9.2/10 on MAL) and continued popularity with multiple seasons and a feature film, *Overlord: The Sacred Kingdom* (2024), highlighting its enduring appeal."
            },
            {
                "id": 29,
                "title": "Horimiya",
                "year": "2021",
                "rating": "8.2",
                "image": "https://i.pinimg.com/736x/86/62/4b/86624b5cec4c124d661792faad4b4e1b.jpg",
                "modalImage": "https://i.pinimg.com/1200x/15/e4/62/15e462466c93029dff820a951f153f55.jpg",
                "category": "New, Comedy",
            "description": "Two high school students with hidden sides develop a relationship.",
            "insights": "Horimiya beautifully and effortlessly balances slice‑of‑life moments with subtle emotional undercurrents, revealing how two seemingly opposite characters grow together. It explores Miyamura’s hidden softer side and Hori’s vulnerabilities, illustrating how authentic connection emerges when masks fall away. The series thrives on its nuanced portrayal of friendship and young love, using humor and silences to capture the excitement and insecurity of adolescence. Supporting characters develop, enriching the central relationship with varied perspectives on identity and acceptance. With its animation and relatable storytelling, Horimiya invites viewers to celebrate the beauty of everyday bonds and the courage it takes to be truly seen."
            },
            {
                "id": 30,
                "title": "Kuroko’s Basketball",
                "year": "2012",
                "rating": "8.10",
                "image": "https://i.pinimg.com/736x/c1/17/99/c11799f120933b30a215cbfb84c1221c.jpg",
                "modalImage": "https://i.pinimg.com/736x/e9/c7/7b/e9c77b9923ae585a0773b06b7f053b17.jpg",
                "category": "Drama, School, Sports, Action, Shonen",
            "description": "Tetsuya Kuroko, the 'phantom' sixth member of a legendary middle school basketball team, joins Seirin High to help them rise to the top by countering super‑skilled opponents.",
            "insights": "Kuroko’s Basketball delivers high‑energy, emotionally charged sports action with flashy super‑moves and intense rivalries. It emphasizes teamwork, underdog spirit, and dramatic court battles. While realism takes a backseat to spectacle, fans frequently rate it as their #1 sports anime—e.g., one Redditor said: \n> “Most matches felt like Haikyuu S3, which is peak Haikyuu… Every time I imagine it shivers are sent down my spine.” :contentReference[oaicite:1]{index=1}\nDespite some animation shortcuts, its hype and character bonds make it a genre staple. :contentReference[oaicite:2]{index=2}"
            },
            {
                "id": 31,
                "title": "Chihayafuru",
                "year": "2011",
                "rating": "9.20",
                "image": "https://i.pinimg.com/736x/90/5c/1c/905c1c88c55f76411b4da5db6258c351.jpg",
                "modalImage": "https://i.pinimg.com/736x/14/fd/01/14fd0152aa7bd959d24ec1f756a79cae.jpg",
                "category": "Top, Romance, Slice-of-life, Drama, Josei, Shojo",
            "description": "Chihaya Ayase discovers a passion for competitive karuta and, alongside childhood friends Taichi and Arata, forms a high school club aiming for national championships.",
            "insights": "Chihayafuru is a heartfelt blend of competitive spirit and emotional depth, focused on the traditional card game karuta. Its strong character development, especially among the central trio, and its portrayal of passion, friendship, and growth have resonated deeply with fans. Reviewers praise its compelling matches and character bonds—one Redditor called it “one of the best binge watches i ever had” while another wrote: \n> “I had never heard of karuta before ... but it was so good that I didn’t care too much for the romance.” :contentReference[oaicite:0]{index=0}",
            },
            {
                "id": 32,
                "title": "Haikyu!!",
                "year": "2014",
                "rating": "9.20",
                "image": "https://i.pinimg.com/1200x/5a/8f/f4/5a8ff474023660890d9cc6a243c0ab4f.jpg",
                "modalImage": "https://i.pinimg.com/736x/05/fc/be/05fcbeebbd62e2094759527b6a33cd4d.jpg",
                "category": "Shonen, School, Sports, Comedy, Drama",
            "description": "Shōyō Hinata, inspired by 'The Little Giant,' joins Karasuno High’s volleyball team alongside rival-turned-teammate Tobio Kageyama, aiming to elevate the school’s volleyball legacy.",
            "insights": "Haikyu!! combines high-octane volleyball action with richly-drawn characters and themes of teamwork, perseverance, and growth. Its strategic match sequences are grounded in emotional stakes, making each rally intense and meaningful. Not just about winning, it celebrates the collective spirit—every teammate and rival arc feels earned—giving it a resonant impact on fans worldwide."
            },
            {
                "id": 33,
                "title": "Fruits Basket",
                "year": "2019",
                "rating": "9.20",
                "image": "https://i.pinimg.com/736x/9e/44/4e/9e444ef3b1cb9bb22f58e8e1c2ca25eb.jpg",
                "modalImage": "https://i.pinimg.com/736x/a6/0e/90/a60e90ee4b255d52ebf15971aecc9b46.jpg",
                "category": "Drama, Slice-of-life, Supernatural, Josei, Shojo, Romance, Fantasy",
            "description": "After a family tragedy, Tohru Honda becomes entwined with the Sohma family, cursed to transform into zodiac animals when hugged, uncovering their emotional wounds.",
            "insights": "Fruits Basket is a deeply emotional and healing story about trauma, empathy, and family bonds. Its warm yet realistic character arcs resonate as one Redditor described:  \n> “wow… matches and forms unconditional bonds … simply fantastic” :contentReference[oaicite:0]{index=0}.  \nWhile it tackles heavy themes like abuse and identity, it balances melancholy with warmth, making it one of the highest‑rated josei anime overall."
            },
            {
                "id": 34,
                "title": "Dragon Ball Z",
                "year": "1989",
                "rating": "8.75",
                "image": "https://i.pinimg.com/1200x/5c/ce/9e/5cce9e0ad9e97fc89d76af75889d4751.jpg",
                "modalImage": "https://i.pinimg.com/1200x/f4/c1/75/f4c17566ba23fda3612d073e3e4f2316.jpg",
                "category": "Action, Adventure, Shonen, Martial arts, Supernatural",
            "description": "Goku and the Z Fighters protect Earth from escalating threats—powerful aliens, androids, and cosmic villains—as they push their limits in epic battles.",
            "insights": "Iconic for its high‑intensity fight scenes, memorable power‑ups, and enduring themes of friendship and perseverance, Dragon Ball Z defined a generation of shounen anime. Its fusion, spirit bomb, and Saiyan transformations remain cornerstones of anime culture worldwide."
            },
            {
                "id": 35,
                "title": "Yu Yu Hakusho",
                "year": "1992",
                "rating": "8.85",
                "image": "https://i.pinimg.com/1200x/5d/f2/39/5df239efb589e6393616be46b8b25fe7.jpg",
                "modalImage": "https://i.pinimg.com/1200x/0b/b0/16/0bb01640e238a845760e76c300160a15.jpg",
                "category": "Action, Supernatural, Martial arts, Shonen, Adventure",
            "description": "Spirit detective Yusuke Urameshi solves supernatural mysteries and fights demons, ascending through the Human World Tournament to the Dark Tournament.",
            "insights": "Yu Yu Hakusho blends street‑style martial arts with spiritual intrigue and tournament drama. Yusuke’s journey from delinquent to hero is marked by strong character bonds, humor, and high‑stakes arcs—making it a foundational 90s shounen classic."
            },
            {
                "id": 36,
                "title": "Fire Force",
                "year": "2019",
                "rating": "8.05",
                "image": "https://i.pinimg.com/1200x/0c/dc/a5/0cdca5678d6ebabfd11cd54a295528ab.jpg",
                "modalImage": "https://i.pinimg.com/736x/cc/9a/e8/cc9ae8b2b6b141e8bcac5b44d95b6683.jpg",
                "category": "Action, Supernatural, Fantasy, Shonen",
            "description": "Special fire brigades combat spontaneous human combustion and infernal beings, as Shinra Kusakabe seeks to uncover the truth behind his family's past.",
            "insights": "Fire Force stands out with its unique premise—blending firefighting, flamethrower powers, and mysterious infernals. Its sleek animation, kinetic battles, and evolving mythology deliver a visually striking and engaging supernatural ride."
            },
            {
                "id": 37,
                "title": "Tokyo Revengers",
                "year": "2021",
                "rating": "8.35",
                "image": "https://i.pinimg.com/736x/30/68/7f/30687f8cda31b23c48eb8382f5926aac.jpg",
                "modalImage": "https://i.pinimg.com/736x/e0/91/97/e091978324fc780f2f6fe8c221c965c3.jpg",
                "category": "Time travel, Gang, Action, Drama, Shonen",
            "description": "Takemichi travels back in time to his middle‑school years to save his ex‑girlfriend and dismantle the Tokyo Manji Gang from within.",
            "insights": "Tokyo Revengers combines gritty delinquent drama with time‑travel stakes, grounding its gang conflicts in emotional motivations. Its raw character flaws and redemption arcs give it a unique emotional and moral complexity in the shounen genre."
            },
            {
                "id": 38,
                "title": "Sailor Moon",
                "year": "1992",
                "rating": "7.7",
                "image": "https://i.pinimg.com/736x/d0/58/f3/d058f39dbd932a5a6c13b707950e90c5.jpg",
                "modalImage": "https://i.pinimg.com/1200x/b8/6e/45/b86e45d57267ea0d67a04c40aed03c21.jpg",
                "category": "Magical girl, Fantasy, Shojo, Shonen, Superhero, Slice-of-life",
            "description": "Usagi Tsukino transforms into Sailor Moon and, with fellow Sailor Guardians, defends the Earth from dark forces while navigating teenage life.",
            "insights": "Sailor Moon revolutionized the magical girl genre with its blend of action, friendship, and coming-of-age storytelling. Its themes of empowerment, team bonds, and identity have influenced countless series. While it features episodic “monster-of-the-day” battles and reused animation—which some fans critique—many appreciate its heartfelt moments and cultural legacy.❝I understand…I as a 21 year old man love this show!…Anyone can be a moonie. Men can enjoy it too.” :contentReference[oaicite:0]{index=0}"
            },

            {
                "id": 39,
                "title": "Mashle: Magic and Muscles",
                "year": "2023",
                "rating": "7.90",
                "image": "https://i.pinimg.com/1200x/2a/23/ce/2a23ce8792971b81e190be856033d3d0.jpg",
                "modalImage": "https://i.pinimg.com/736x/8d/72/33/8d723378cadb85e4b42c138e56783775.jpg",
                "category": "Comedy, Fantasy, Action, Magic, Shonen",
            "description": "In a world of magic, Mash Burnedead relies solely on magical muscles to compete in a prestigious magic academy and protect his loved ones.",
            "insights": "Mashle parodies magic school tropes with ridiculous strength‑based comedy. Its absurd gags, over‑the‑top fights, and lighthearted tone offer a fun, muscular twist on the fantasy genre, while celebrating friendship and determination."
            },
            {
                "id": 40,
                "title": "Gintama",
                "year": "2006",
                "rating": "9.00",
                "image": "https://i.pinimg.com/1200x/6c/6e/a9/6c6ea9de2cdd9e11488a8279fb45b792.jpg",
                "modalImage": "https://i.pinimg.com/1200x/d9/8d/9c/d98d9c6388854d82712427c112b7427f.jpg",
                "category": "Comedy, Action, Sci‑fi, Shonen, Drama, Parody",
            "description": "In an alternate Edo under alien rule, freelancer Gintoki Sakata takes odd jobs with his samurai friends, mixing goofy hijinks and epic swordplay.",
            "insights": "Gintama is a genre-bending marvel—seamlessly shifting between gut‑busting comedy, poignant drama, and action‑packed arcs. Its fourth‑wall jokes, pop culture references, and emotional payoffs have earned it a beloved status among fans of all stripes."
            },
            {
                "id": 41,
                "title": "Fairy Tail",
                "year": "2009",
                "rating": "8.05",
                "image": "https://i.pinimg.com/1200x/e7/a5/cf/e7a5cfd71c32d21f54bf5a20c4664307.jpg",
                "modalImage": "https://i.pinimg.com/736x/03/6e/45/036e45dd718fea1ecc63efcc0a09e3c4.jpg",
                "category": "Action, Fantasy, Shonen, Adventure, Magic",
            "description": "Natsu Dragneel and Lucy Heartfilia join the Fairy Tail guild to take on missions, fight dark wizards, and become stronger alongside loyal friends.",
            "insights": "Fairy Tail celebrates strong bonds, explosive magic action, and heartfelt camaraderie. Its long-running saga combines comedic ensemble moments and emotional arcs, making it a staple of shounen anime despite occasional filler pacing."
            },
            {
                "id": 42,
                "title": "Ouran High School Host Club",
                "year": "2006",
                "rating": "8.2",
                "image": "https://i.pinimg.com/736x/f0/af/4e/f0af4e2f1c183e7c5b259d4fbe35ef69.jpg",
                "modalImage": "https://i.pinimg.com/1200x/1e/73/e1/1e73e1e9512efe6d6385bac3a95a9bf6.jpg",
                "category": "Shojo, Comedy, Romance",
            "description": "Scholarship student Haruhi Fujioka accidentally breaks an expensive vase at Ouran Academy and ends up joining the elite, eccentric Host Club to repay her debt.",
            "insights": "Ouran High School Host Club delights with witty parody of high school tropes and shameless fourth-wall awareness. Its lovable ensemble—led by Haruhi and the princely Tamaki—balances zany humor with moments of genuine warmth. The series explores themes of identity, class contrast, and friendship with both comedic flair and heartfelt sincerity. It remains a beloved shoujo classic that inspired a generation."
            },
            {
                "id": 43,
                "title": "Cardcaptor Sakura",
                "year": "1998",
                "rating": "9.20",
                "image": "https://i.pinimg.com/1200x/4d/d4/53/4dd453e6843e56b728834996e8bac492.jpg",
                "modalImage": "https://i.pinimg.com/1200x/25/97/4f/25974f28aad4981f59163d3c3f73e405.jpg",
                "category": "Magical girl, Fantasy, Shojo, Romance, Adventure",
            "description": "Ten‑year‑old Sakura Kinomoto accidentally releases magical Clow Cards and must collect them with the help of guardian Cerberus and best friend Tomoyo.",
            "insights": "Cardcaptor Sakura is a groundbreaking magical‑girl classic celebrated for its emotional depth, themes of love and friendship, and gorgeous CLAMP artwork. It skillfully blends supernatural adventures with slice‑of‑life moments, empowering its lead while exploring diverse relationships and LGBTQ themes. With its charming characters, heartfelt storytelling, and nostalgic appeal, it remains one of the most beloved series of the late ’90s and early ’00s."
            },
            {
                "id": 44,
                "title": "Yona of the Dawn (Akatsuki no Yona)",
                "year": "2014",
                "rating": "8.00",
                "image": "https://i.pinimg.com/1200x/24/30/81/243081eecceef6605e55e8cd193c534c.jpg",
                "modalImage": "https://i.pinimg.com/1200x/1b/c9/7e/1bc97e27e0a08451e1fe4ea6e3c192ed.jpg",
                "category": "Fantasy, Adventure, Romance, Shojo",
            "description": "Princess Yona flees after a palace coup and, with her loyal bodyguard Hak, embarks on a journey to reclaim her kingdom and awaken legendary dragon warriors.",
            "insights": "Yona’s transformation from sheltered royal to determined leader is compelling, backed by rich world‑building and emotional stakes. A Reddit fan praised its ‘strong worldbuilding, adventure, some angst and good character development’ :contentReference[oaicite:1]{index=1}."
            },
            {
                "id": 45,
                "title": "Snow White with the Red Hair (Akagami no Shirayuki-hime)",
                "year": "2015",
                "rating": "8.30",
                "image": "https://i.pinimg.com/1200x/0e/41/25/0e4125efd2c9db8a567db76aad97ce95.jpg",
                "modalImage": "https://i.pinimg.com/1200x/1b/94/c5/1b94c535eea0c005f97ca5bdc14cf10d.jpg",
                "category": "Romance, Fantasy, Slice-of-life, Shojo",
            "description": "Red‑haired herbalist Shirayuki escapes her country's prince and starts anew in a foreign land, gaining a royal bodyguard and finding love along the way.",
            "insights": "A gentle historical‑Fantasy romance praised for its mature relationship growth, lovely art, and strong heroine. The chemistry and serene tone stand out in the Shojo genre."
            },
            {
                "id": 46,
                "title": "Boys Over Flowers (Hana Yori Dango)",
                "year": "1996",
                "rating": "8.10",
                "image": "https://i.pinimg.com/736x/c1/bd/89/c1bd894de8dc50b53443e3f1a17a5a4b.jpg",
                "modalImage": "https://i.pinimg.com/1200x/4b/86/cc/4b86cc648f94a1477f22677667f2bda9.jpg",
                "category": "Romance, Comedy, Drama, School, Reverse-harem",
            "description": "Scholarship student Tsukushi Makino clashes with the elite F4 at her elite school, sparking an unlikely romance with their leader, Tsukasa Domyouji.",
            "insights": "A pioneering romantic drama in anime, composed of sharp social satire, strong-willed heroine, and iconic character arcs. It's a classic in the reverse-harem/slash genre with enduring influence."
            },
            {
                "id": 47,
                "title": "Blue Spring Ride (Ao Haru Ride)",
                "year": "2014",
                "rating": "8.00",
                "image": "https://i.pinimg.com/736x/51/da/f7/51daf706cec401ff4ca0a2e96f0df0ea.jpg",
                "modalImage": "https://i.pinimg.com/1200x/ab/28/08/ab2808520b46d6143a129a25c90caaeb.jpg",
                "category": "Romance, School, Slice-of-life, Shojo, Drama",
                "description": "High-schooler Futaba reconnects with her first love, Kou, after he changes following family tragedy, as they both learn to navigate adolescence.",
                "insights": "Ao Haru Ride delivers heartfelt nostalgia and emotional honesty, spotlighting themes of growth and reconnecting. Its simple but sincere portrayal of young love resonates with many Shojo fans."
            },
            {
                "id": 48,
                "title": "Wolf Girl and Black Prince (Ōkami Shōjo to Kuro Ōji)",
                "year": "2014",
                "rating": "7.90",
                "image": "https://i.pinimg.com/736x/65/8d/18/658d18aaf7a2588a2ea727dc74be2ac1.jpg",
                "modalImage": "https://i.pinimg.com/736x/aa/06/af/aa06afadfc9fcb815062e113866243a8.jpg",
                "category": "Romance, Comedy, School, Shojo",
            "description": "To appear more popular, Erika lies about having a boyfriend and coerces self‑taken photos with the handsome Kyoya—only to get involved in a fake relationship.",
            "insights": "A playful take on high‑school romance tropes, featuring tsundere chemistry and comedic misunderstandings. Despite some cringe moments, it shines in its character banter and romantic payoff."
            },
            {
                "id": 49,
                "title": "Revolutionary Girl Utena",
                "year": "1997",
                "rating": "8.10",
                "image": "https://i.pinimg.com/1200x/45/51/e0/4551e0f712ad3f5ca3a3da853a35da1d.jpg",
                "modalImage": "https://i.pinimg.com/1200x/ac/97/f4/ac97f44959dc5f5e87235d17b6daf209.jpg",
                "category": "Magical girl, Surreal, Romance, Drama, Shojo",
            "description": "Utena Tenjou, inspired to be a 'prince', enters sword duels to protect the enigmatic 'Rose Bride', challenging gender roles and societal norms.",
            "insights": "Utena is a surreal deconstruction of fairy‑tale tropes and gender roles, layered with symbolism and queer themes. A Redditor called it “one of the most important anime ever made” and praised its depth :contentReference[oaicite:2]{index=2}, and Wikipedia notes its groundbreaking LGBTQ‑positive narrative :contentReference[oaicite:3]{index=3}."
            },
            {
                "id": 50,
                "title": "Psycho‑Pass",
                "year": "2012",
                "rating": "8.40",
                "image": "https://i.pinimg.com/736x/cc/b2/67/ccb267cd1894ffb6f6ce42f561a1f85a.jpg",
                "modalImage": "https://i.pinimg.com/1200x/b4/63/65/b463651ba6c5575892470cd3dd1b237b.jpg",
                "category": "Seinen, Sci‑fi, Crime, Psychological, Dystopian",
            "description": "In a future where a system quantifies mental states to prevent crime, officers enforce justice as latent criminals threaten societal order.",
            "insights": "Psycho‑Pass explores morality under surveillance, raising disturbing questions about free will and authoritarianism. With strong female leads and cerebral crime plots, it's a compelling philosophical thriller that shaped modern cyberpunk anime."
            },
            {
                "id": 51,
                "title": "91 Days",
                "year": "2016",
                "rating": "7.60",
                "image": "https://i.pinimg.com/736x/d6/59/ca/d659ca9f1068adedf446c0e93c318ca2.jpg",
                "modalImage": "https://i.pinimg.com/1200x/8f/eb/fd/8febfd3c2eb65f6c90ea986455abf465.jpg",
                "category": "Seinen, Crime, Dram, Historical, Mafia",
            "description": "During Prohibition in the U.S., Angelo infiltrates the mafia to enact revenge for his family's murder, walking a narrow path of betrayal.",
            "insights": "91 Days is a tight 12‑episode noir revenge tale, praised for its atmosphere, character betrayal, and tragic twists. IMDb users call it a “hidden diamond” :contentReference[oaicite:5]{index=5}."
            },
            {
                "id": 52,
                "title": "Durarara!!",
                "year": "2010",
                "rating": "8.20",
                "image": "https://i.pinimg.com/1200x/9c/0f/16/9c0f1624e8f86211fb3f739d8f28972c.jpg",
                "modalImage": "https://i.pinimg.com/1200x/4b/f8/6f/4bf86fd67e75bb0de101a1d61dda3b43.jpg",
                "category": "Seinen, Urban, Supernatural, Mystery, Action",
            "description": "In Ikebukuro, an ensemble cast’s lives intertwine through a headless biker, urban legends, gang conflicts, and supernatural threads.",
            "insights": "Durarara!! is celebrated for its multi‑threaded storytelling, vibrant urban setting, and mix of supernatural with slice‑of‑life. Its overlapping narratives keep viewers guessing and grounded in energetic city life."
            },
            {
                "id": 53,
                "title": "Hellsing Ultimate",
                "year": "2006",
                "rating": "9.10",
                "image": "https://i.pinimg.com/736x/33/1f/a0/331fa01e5ddf4b727c52dc88f29915c5.jpg",
                "modalImage": "https://i.pinimg.com/1200x/87/48/4a/87484aa11873736e36da94b9890234aa.jpg",
                "category": "Seinen, Action, Horror, Supernatural, Vampire",
            "description": "The Hellsing Organization battles vampires and ghouls in this ultra‑violent reimagining of vampire lore, led by the powerful vampire Alucard.",
            "insights": "Hellsing Ultimate is praised for its stylish gore, dark tone, and Alucard’s charisma. Its mature, unapologetic violence and slick animation make it a benchmark vampire action anime."
            },
            {
                "id": 54,
                "title": "Black Lagoon",
                "year": "2006",
                "rating": "8.20",
                "image": "https://i.pinimg.com/736x/cb/59/f6/cb59f6b0b25f76c46175b28f11e98cac.jpg",
                "modalImage": "hhttps://i.pinimg.com/736x/34/96/0f/34960f6c776ead42adb1bc6939da780c.jpg",
                "category": "Seinen, Action, Crime, Gang",
                "description": "A Japanese businessman turned pirate joins the Lagoon Company, a mercenary crew in Southeast Asia, navigating criminal underworld operations.",
            "insights": "Black Lagoon is lauded for its gritty realism, intense gun‑fights, and morally ambiguous characters. Its exploration of anti‑heroes in a chaotic underworld sets it apart in crime‑action anime."
            },

            {
                "id": 55,
                "title": "Kakegurui – Compulsive Gambler",
                "year": "2017",
                "rating": "8.0",
                "image": "https://i.pinimg.com/1200x/e6/5d/d7/e65dd7c8398040a7db98db5c11957467.jpg",
                "modalImage": "https://i.pinimg.com/1200x/fd/64/0c/fd640ca795e30d61fcf494812611c2e2.jpg",
                "category": "Psychological, Thriller, School, Drama, Shonen, Mystery",
            "description": "Yumeko Jabami transfers to Hyakkaou Private Academy, a school where social status is determined by gambling—she gambles not for money, but for the thrill of life‑or‑death stakes.",
            "insights": "Kakegurui flips school hierarchy into high‑stakes gambling, with each match testing psychological endurance, risk, and power dynamics. It’s visually intense with MAPPA’s exaggerated animation and a magnetic lead in Yumeko. While fans praise its exploration of addiction, status games, and the rush of chance :contentReference[oaicite:1]{index=1}, others note repetitive structure and excessive fan‑service :contentReference[oaicite:2]{index=2}."
            },

            {
                "id": 56,
                "title": "Vinland Saga",
                "year": "2019",
                "rating": "9.20",
                "image": "https://i.pinimg.com/1200x/cd/b3/e1/cdb3e1ddcca1fdaa27d8e61e7ea3ae49.jpg",
                "modalImage": "https://i.pinimg.com/736x/3c/6b/e0/3c6be06917e3589f4b182ba9668bde61.jpg",
                "category": "Seinen, Action, Historical, Drama, Adventure",
            "description": "Thorfinn, son of a slain warrior, grows in a brutal Viking world, evolving from revenge seeker to a fighter for peace.",
            "insights": "Vinland Saga is praised for its philosophical depth, realistic combat, and Thorfinn’s emotional arc toward honor and redemption. Its mature tone and stunning animation have made it a modern classic :contentReference[oaicite:2]{index=2}. One Reddit fan said it’s “exactly what you’re looking for” if you like Berserk :contentReference[oaicite:3]{index=3}."
            },
            {
                "id": 57,
                "title": "Tokyo Ghoul",
                "year": "2014",
                "rating": "7.90",
                "image": "https://i.pinimg.com/736x/35/5d/eb/355deb88738f4eaf38d2c95a3972a7c2.jpg",
                "modalImage": "https://i.pinimg.com/1200x/4a/e7/1a/4ae71ac778e86490d312ebe4b7b139c0.jpg",
                "category": "Seinen, Dark fantasy, Horror, Supernatural, Drama",
            "description": "College student Kaneki becomes a half-ghoul and must navigate the violent world of ghouls while struggling with his humanity.",
            "insights": "Tokyo Ghoul is known for its gritty atmosphere and internal conflict, charting Kaneki’s violent transformation and identity struggle. Though its second season diverges from the manga, it remains popular for its bold visuals and tragic tone :contentReference[oaicite:4]{index=4}."
            },
            {
                "id": 58,
                "title": "Monster",
                "year": "2004",
                "rating": "9.2",
                "image": "https://i.pinimg.com/736x/54/80/82/54808234fe35dd18c6882b07a34ff641.jpg",
                "modalImage": "https://i.pinimg.com/1200x/63/45/71/634571dc4a0c5440241f92dab0d85eed.jpg",
                "category": "Seinen, Psychological, Mystery, Crime, Thriller, Drama",
            "description": "After saving the life of a young boy who later becomes a serial killer, Dr. Kenzo Tenma pursues him across Europe, wrestling with guilt and chasing justice.",
            "insights": "Monster unfolds as a masterful psychological thriller that examines morality, guilt, and human darkness with surgical precision. Its richly complex characters—especially the enigmatic Johan and conflicted Tenma—evolve amid a slow‑burn plot that grips viewers in a moral labyrinth. Lauded as ‘one of the best anime of all time’ with immersive writing, unforgettable villains, and depth beyond genre norms, it’s a haunting exploration of human nature. (<100 words)"
            },
            {
                "id": 59,
                "title": "Berserk",
                "year": "1997",
                "rating": "9.2",
                "image": "https://i.pinimg.com/1200x/b9/e8/27/b9e827fb9380caa2475b93daaececaa3.jpg",
                "modalImage": "https://i.pinimg.com/736x/d9/ca/67/d9ca679e5874fabb2cba91437c767a66.jpg",
                "category": "Seinen, Dark fantasy, Action, Horror",
            "description": "Guts, a lone mercenary wielding the massive Dragonslayer blade, battles demons and betrayal in a brutal medieval world, driven by revenge and survival.",
            "insights": "Berserk captivates with its profoundly dark and mature storytelling, exploring fate, trauma, and the indomitable will of humanity. Guts’ metamorphic journey—from vengeance‑driven mercenary to philosophical survivor—paired with Susumu Hirasawa’s haunting soundtrack, crafts an atmospheric masterpiece. While its animation aging shows, fans praise its emotional resonance, philosophical depth, and brutal visual poetry, affirming its legendary status in anime history."
            },
            {
                "id": 60,
                "title": "Orange",
                "year": "2016",
                "rating": "8.0",
                "image": "https://i.pinimg.com/736x/f3/a2/db/f3a2db94d46b2e8a8dfb4159d8d3fdfa.jpg",
                "modalImage": "https://i.pinimg.com/1200x/df/b3/6c/dfb36c0b8da769ca9fe434ed25a45985.jpg",
                "category": "Seinen, Slice-of-life, Drama, Romance, Supernatural, School",
            "description": "Naho Takamiya receives letters from her future self, urging her to save Kakeru Naruse and prevent future regrets.",
            "insights": "Orange is a poignant, time‑traveling high‑school drama exploring themes like friendship, regret, and mental health. Over its 13 episodes, it builds toward an emotional climax, with many fans calling it an ‘emotional roller coaster’ and recommending tissues at the ready."
            },
            {
                "id": 61,
                "title": "Noragami",
                "year": "2014",
                "rating": "9.20",
                "image": "https://i.pinimg.com/736x/38/72/5a/38725ad76e8cf93ac691467c135b812a.jpg",
                "modalImage": "https://i.pinimg.com/1200x/d3/ff/b5/d3ffb5e1115bfb402f02405bf23b40b2.jpg",
                "category": "Adventure, Shonen, Supernatural, Action, Comedy",
            "description": "Yato, a down‑and‑out god offering odd jobs for 5 yen, meets Hiyori whose soul becomes untethered, and they partner with his Regalia Yukine to battle malevolent spirits.",
            "insights": "Noragami shines by blending quirky comedy and supernatural action with unexpectedly deep emotional themes. Yato’s journey from comic-relief ‘Delivery God’ to emotionally complex deity, coupled with Hiyori’s soul‑straddling dilemma and Yukine’s redemption arc, create a strong character-driven core. Its dark turns—touching on death, guilt, and identity—are balanced by lighthearted moments and stylish visuals. Highly praised for nuanced storytelling and polished animation despite some pacing dips, it's considered a modern cult favorite."
            },
            {
                "id": 62,
                "title": "Mob Psycho 100",
                "year": "2016",
                "rating": "9.20",
                "image": "https://i.pinimg.com/736x/39/17/f2/3917f2c899f6a4486b203f11f90a54c7.jpg",
                "modalImage": "https://i.pinimg.com/1200x/5a/91/82/5a918288ab22b86aecb92c99a2212acd.jpg",
                "category": "Psychological, Shonen, Supernatural, Comedy, Action",
            "description": "Shigeo “Mob” Kageyama is a powerful young psychic trying to live an ordinary life, balancing his abilities with emotional growth and human connection.",
            "insights": "Mob Psycho 100 combines stunning, experimental animation with deep emotional themes, showcasing Mob’s struggle to control immense psychic power through empathy, mentorship, and self-discovery. Its life lessons—like valuing communication over violence, accepting both strengths and weaknesses, and the power of personal growth—shine across its three seasons. It has won accolades for its action, animation, and characters, and is frequently praised as one of the best anime of the 2010s."
            },
            {
                "id": 63,
                "title": "Made in Abyss",
                "year": "2017",
                "rating": "8.9",
                "image": "https://i.pinimg.com/1200x/bd/9b/83/bd9b83cc735e60c9dce6c1d5457fd5ed.jpg",
                "modalImage": "https://i.pinimg.com/1200x/78/fa/7b/78fa7b0c7787d02b5d4721bd54029120.jpg",
                "category": "Dark fantasy, Sci-fi, Adventure, Fantasy, Mystery",
            "description": "Young orphan Riko and adorable robot Reg descend into the Abyss—a mysterious, danger-filled chasm—to find Riko’s mother and unravel its hidden secrets.",
            "insights": "Made in Abyss boasts breathtaking, almost deceptive art that belies its intense emotional and thematic depth. With stunning world-building and morally complex storytelling, it explores themes of curiosity, sacrifice, and the fragility of innocence. Its carefully paced mix of wonder and horror combined with unforgettable characters and immersive environments solidifies it as one of the most impactful anime of the 2010s."
            },
            {
                "id": 64,
                "title": "Mushoku Tensei: Jobless Reincarnation",
                "year": "2021",
                "rating": "8.83",
                "image": "https://i.pinimg.com/1200x/51/18/72/511872fadf2afbd31818b4953ae5fa41.jpg",
                "modalImage": "https://i.pinimg.com/1200x/5a/25/cd/5a25cd0650c8d0643e231c8397d6d7f7.jpg",
                "category": "Fantasy, Adventure, Drama, Isekai, Magic",
            "description": "Rudeus Greyrat is reincarnated in a magical world retaining his past memories and is determined to live without regrets—facing both extraordinary power and personal reckoning.",
            "insights": "Mushoku Tensei revolutionized the isekai genre with its deeply flawed yet evolving protagonist, rich world-building, and emotional realism. While its early arcs contain controversial moments, the series is widely praised for Rudeus’s character growth—from trauma to maturity—and its thoughtful exploration of regret, redemption, and human relationships. Fans call it a masterpiece that speaks to modern societal issues and ranks as the top isekai among Reddit communities."
            },
            {
                "id": 65,
                "title": "Yuri!!! on Ice",
                "year": "2016",
                "rating": "9.20",
                "image": "https://i.pinimg.com/736x/58/dc/cb/58dccb75296f2eb6b25679b9b1899b5c.jpg",
                "modalImage": "https://i.pinimg.com/1200x/e5/bc/fb/e5bcfbf6a35a84e59fb3735e6a5869b3.jpg",
                "category": "Sports, Romance, Drama, Slice‑of‑life",
            "description": "Japanese figure skater Yuri Katsuki battles self‑doubt after a crushing loss. With the support of Russian champion Victor Nikiforov as his coach—and rival Yurio—Yuri aims to reclaim his confidence on ice and in life.",
            "insights": "Yuri!!! on Ice is a groundbreaking sports anime that blends stunning rotoscoped figure‑skating animation with a heartfelt same‑sex romance. It balances competitive drive, emotional introspection, and LGBTQ+ representation deftly. With its iconic ‘History Maker’ opening, award‑winning visuals, and character chemistry, it became the first anime to sweep all seven categories at the 2017 Crunchyroll Anime Awards.❝The animation is fantastic… professional skaters have confirmed… the animators went out of their way to change each program… an amazing feat❞ :contentReference[oaicite:2]{index=2}."
            },
            {
                "id": 66,
                "title": "Mononoke",
                "year": "2007",
                "rating": "8.9",
                "image": "https://i.pinimg.com/736x/ae/e5/aa/aee5aac8d9f808ace48579790f31d8bb.jpg",
                "modalImage": "https://i.pinimg.com/1200x/cb/38/35/cb38359737823ebc460b411bd1824c49.jpg",
                "category": "Psychological, Seinen, Mystery, Supernatural, Horror",
            "description": "An enigmatic Medicine Seller travels Edo‑era Japan, exorcising malevolent spirits by uncovering their Form, Truth, and Reason.",
            "insights": "Mononoke stands out as a psychedelic horror‑mystery, melding Ukiyo‑e inspired visuals with episodic tales that explore guilt, human trauma, and folklore. Each arc is a twisted detective puzzle where the Medicine Seller must discern a spirit’s true nature before using his sword. Its surreal art, symbolic storytelling, and haunting atmosphere make it a cult classic—revived with a Netflix trilogy and praised for its bold, experimental style."
            },
            {
                "id": 67,
                "title": "Kaguya‑sama: Love is War",
                "year": "2019",
                "rating": "8.7",
                "image": "https://i.pinimg.com/736x/2c/20/4e/2c204ec13ab1282fdedf09cad93ff076.jpg",
                "modalImage": "https://i.pinimg.com/1200x/57/ad/96/57ad964c08d34e44a5d7762338005a8a.jpg",
                "category": "Comedy, Romance, School, Slice‑of‑life, Seinen",
            "description": "Elite student council leaders Kaguya Shinomiya and Miyuki Shirogane wage psychological war to force the other into confessing first.",
            "insights": "Smart, hilarious, and heartfelt—Kaguya‑sama is a game of emotional chess. With razor‑sharp wit, top‑tier animation by A‑1 Pictures, and chemistry that keeps evolving, it's topped user‑rated charts (average ~8.7/10 on IMDb and MAL) and swept Best Comedy and Best Couple at the Crunchyroll Anime Awards :contentReference[oaicite:0]{index=0}."
            },
            {
                "id": 68,
                "title": "Nichijou (My Ordinary Life)",
                "year": "2011",
                "rating": "8.3",
                "image": "https://i.pinimg.com/1200x/cb/af/d6/cbafd647ce45dd865b131b516594227c.jpg",
                "modalImage": "https://i.pinimg.com/736x/51/af/2a/51af2a6eb5e111f7d17adbaaf259a9de.jpg",
                "category": "Comedy, Slice of Life, School",
            "description": "Everyday moments spin out of control when three girls and a robot professor live through absurd, over‑the‑top scenarios.",
            "insights": "Nichijou is Kyoto Animation’s surreal slice‑of‑life comedy mastered through kinetic visuals and exponential lunacy. It maintains an 8.3/10 IMDb rating :contentReference[oaicite:1]{index=1} and earned cult status with Anime News Network calling it “one of the finest anime comedies of all time” :contentReference[oaicite:2]{index=2}."
            },
            {
                "id": 69,
                "title": "Natsume’s Book of Friends (Natsume Yūjin‑chō)",
                "year": "2008",
                "rating": "8.5",
                "image": "https://i.pinimg.com/736x/b7/f0/44/b7f04420a7e80908378a50a1499aed01.jpg",
                "modalImage": "https://i.pinimg.com/1200x/c4/bf/72/c4bf728492f128e19174abbac63ced19.jpg",
                "category": "Supernatural, Slice of Life, Drama, Fantasy",
            "description": "Takashi Natsume inherits a book of bound spirits and seeks to release them while forging bonds between humans and yōkai.",
            "insights": "Natsume’s Book of Friends blends gentle supernatural storytelling with emotional character‑driven narratives. Known for its soothing tone, empathy, and exploration of loneliness and belonging, it’s consistently praised as a heartfelt standout in supernatural slice‑of‑life anime."
            },
            {
                "id": 70,
                "title": "Megalo Box",
                "year": "2018",
                "rating": "8.5",
                "image": "https://i.pinimg.com/1200x/56/c2/10/56c2100d53e0f8dcdbe4f0b8f5ba5d56.jpg",
                "modalImage": "https://i.pinimg.com/736x/77/83/42/778342abac87bcd67673e691b597c086.jpg",
                "category": "Sports, Drama, Action, Boxing, Sci-fi",
            "description": "In a futuristic boxing world, underdog gearless fighter Junk Dog rises through the ranks in Megalo Boxing, defying the class hierarchy.",
            "insights": "Megalo Box is a stylish, nostalgic homage to Ashita no Joe. With gritty animation, deep character arcs, and a retro-futuristic aesthetic, it delivers an emotional knockout punch."
            },

            {
                "id": 71,
                "title": "SK8 the Infinity",
                "year": "2021",
                "rating": "8.5",
                "image": "https://i.pinimg.com/736x/b5/a5/85/b5a585e3e9fe213a80d09d513b602d38.jpg",
                "modalImage": "https://i.pinimg.com/1200x/7d/19/e2/7d19e2538d998da5f851ba0b626592a3.jpg",
                "category": "Sports, Adventure, Drama, Skateboarding",
            "description": "Reki introduces transfer student Langa to 'S', a reckless midnight downhill skateboard race in Okinawa’s secret tunnels.",
            "insights": "SK8 the Infinity blends extreme skateboarding action with character-driven drama. The fluid animation and emotional storytelling earned it fan acclaim—“blown away… I wait every Saturday” :contentReference[oaicite:2]{index=2}."
            },

            {
                "id": 72,
                "title": "Salaryman's Club",
                "year": "2022",
                "rating": "7.8",
                "image": "https://i.pinimg.com/1200x/73/18/52/731852188e2390d80900bc127434fde2.jpg",
                "modalImage": "https://i.pinimg.com/1200x/92/7b/b5/927bb576448b0ff44d4469057b6bab61.jpg",
                "category": "Sports, Novelty, Slice-of-life, Business",
            "description": "Office workers form a badminton team to challenge their superior and revive their spirits through workplace sports.",
            "insights": "Salaryman’s Club mixes corporate satire with unexpected badminton enthusiasm. It offers refreshing humor and camaraderie, spotlighting adult life pressures and the joy of rediscovery."
            },

            {
                "id": 73,
                "title": "Blue Box (Ao no Hako)",
                "year": "2024",
                "rating": "9.2",
                "image": "https://i.pinimg.com/736x/ce/69/57/ce6957cc76ac21056f0074a7cec4881a.jpg",
                "modalImage": "https://i.pinimg.com/1200x/d9/38/8b/d9388bd152021d21081efe08219dd26e.jpg",
                "category": "Romance, Sports, Slice-of-life, School",
            "description": "High school badminton player Taiki and rising basketball star Chinatsu develop affection as they balance personal dreams and shared practice sessions.",
            "insights": "Blue Box is praised for its authentic teenage romance intertwined with sports passion. The anime’s opener 'Saraba' has been lauded as the best of Winter 2025 on Netflix :contentReference[oaicite:0]{index=0}. A Reddit fan shared: \n> “I’ve never been soo passionate about watching an anime… I smile I giggle I sad I angry… it’s so good.” :contentReference[oaicite:1]{index=1}"
            },

            {
                "id": 74,
                "title": "Ahiru no Sora",
                "year": "2019",
                "rating": "7.95",
                "image": "https://i.pinimg.com/1200x/a6/24/ed/a624edbf1d375f5a3b8e8e56e902e3bb.jpg",
                "modalImage": "https://i.pinimg.com/736x/9f/ae/f7/9faef7bbf0a6f010ebf6f90b80bf922c.jpg",
                "category": "Sports, Basketball, Shonen, School",
            "description": "Short-statured Sora leads his high school's basketball team, overcoming physical limitations and team cliques with grit and heart.",
            "insights": "Ahiru no Sora delivers classic underdog basketball drama. It balances intense court play with themes of perseverance and friendship—earning a loyal fanbase despite niche popularity."
            },

            {
                "id": 75,
                "title": "Baki Hanma",
                "year": "2021",
                "rating": "8.00",
                "image": "https://i.pinimg.com/1200x/0a/b7/5a/0ab75adc62c2ff53ca35fa9a59c7b471.jpg",
                "modalImage": "https://i.pinimg.com/1200x/e0/44/61/e04461f9e38ff870de868d5846582882.jpg",
                "category": "Action, Martial arts, Sports, Seinen",
            "description": "Baki prepares for the ultimate showdown: a no-rules match against his father Yujiro, the world’s strongest fighter.",
            "insights": "Baki Hanma features brutal, visceral martial arts and hyper-stylized combat. Its relentless intensity, over-the-top violence, and raw focus on strength push the limits of fight anime."
            }
            ]

            for anime in anime_data:
                cursor.execute('''
                            INSERT INTO anime (id, title, year, rating, image, modalImage, category, description, insights)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                    anime['id'],
                    anime['title'],
                    anime['year'],
                    anime['rating'],
                    anime['image'],
                    anime['modalImage'],
                    anime['category'],
                    anime['description'],
                    anime['insights']
                ))
            db.commit()

            cursor.execute("SELECT COUNT(*) FROM movies")
            if cursor.fetchone()[0] == 0:
                movies_data = [
                    # Your movie data goes here (all 26 entries)
                    {
                        "id": 76,
                        "title": "Weathering With You",
                        "year": "2019",
                        "rating": "7.5",
                        "image": "https://i.pinimg.com/736x/de/4e/01/de4e0140ecdce63e20abb54720d397e4.jpg",
                        "modalImage": "https://i.pinimg.com/736x/e6/7a/10/e67a10863ace14b5a7fc2edb5db38158.jpg",
                        "category": "fantasy,romance,drama,supernatural,featured,new,award",
                        "description": "A runaway boy meets a girl who can control the weather, sparking a magical connection and moral dilemmas.",
                        "insights": "A visually stunning spiritual companion to Your Name, this film deepens Shinkai's exploration of youth and fate. Critics praised its animation and emotion, with generally favorable reviews :contentReference[oaicite:4]{index=4}.",
                        "director": "Makoto Shinkai",
                        "duration": "112 min"
                    },
                    {
                        "id": 77,
                        "title": "I Want To Eat Your Pancreas",
                        "year": "2018",
                        "rating": "8.62",
                        "image": "https://i.pinimg.com/1200x/aa/49/49/aa4949a1fd89af58809d66babe5e2d11.jpg",
                        "modalImage": "https://i.pinimg.com/736x/42/7c/ad/427cad84e6b5965a6a600716dc108a25.jpg",
                        "category": "drama, romance, school, featured",
                    "description": "A shy boy reads a classmate’s secret terminal illness diary and they form a life‑affirming bond.",
                "insights": "A tender and tragic journey about friendship, mortality, and living fully. Emotional depth and mature storytelling earned strong praise and an ~8.6 MAL rating :contentReference[oaicite:5]{index=5}.",
                "director": "Shinichiro Ushijima",
                "duration": "109 min"
                },

                {
                    "id": 78,
                    "title": "Spirited Away",
                    "year": "2001",
                    "rating": "8.93",
                    "image": "https://i.pinimg.com/736x/4a/ac/48/4aac48897954fdd44fa81be2200b7fad.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/9b/e6/34/9be6345125b34db8a7a314b682c4f7e3.jpg",
                    "category": "fantasy, adventure, supernatural, ghibli, award",
                "description": "Chihiro enters a magical world of spirits and must save her parents and return home.",
                "insights": "Hayao Miyazaki’s Oscar‑winning classic remains a benchmark in imagination and character, blending folklore, growth, and visual wonder into an unforgettable coming‑of‑age tale.",
                "director": "Hayao Miyazaki",
                "duration": "125 min"
                },

                {
                    "id": 79,
                    "title": "Howl's Moving Castle",
                    "year": "2004",
                    "rating": "8.54",
                    "image": "https://i.pinimg.com/736x/76/23/77/762377766d63e84b89b07a400968a753.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/9c/1f/ab/9c1fab6167dadbff7363c8826a087c2d.jpg",
                    "category": "fantasy, romance, adventure, ghibli",
                "description": "A shy girl cursed into old age by a witch befriends a mysterious wizard and his walking castle.",
                "insights": "A lush, anti‑war fantasy with catalytic character transformations and surreal visuals—another Miyazaki masterpiece weaving magic, heart, and social commentary.",
                "director": "Hayao Miyazaki",
                "duration": "119 min"
                },

                {
                    "id": 80,
                    "title": "Princess Mononoke",
                    "year": "1997",
                    "rating": "8.89",
                    "image": "https://i.pinimg.com/736x/ae/e5/aa/aee5aac8d9f808ace48579790f31d8bb.jpg",
                    "modalImage": "https://i.pinimg.com/736x/ca/b2/b9/cab2b976d9a623418776deac5587d49d.jpg",
                    "category": "fantasy, adventure, epic, ghibli, award",
                "description": "A young warrior becomes embroiled in a conflict between humans and the gods of the forest.",
                "insights": "A powerful ecological epic that pits human ambition against nature’s spirits, packed with complex morality, stunning art, and an iconic soundtrack.",
                "director": "Hayao Miyazaki",
                "duration": "134 min"
                },

                {
                    "id": 81,
                    "title": "My Neighbor Totoro",
                    "year": "1988",
                    "rating": "8.32",
                    "image": "https://i.pinimg.com/736x/d1/2c/ad/d12cadc3f62500594821be0278aef5a8.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/81/84/8e/81848e68aef12dd207b299f9d0f198dd.jpg",
                    "category": "slice‑of‑life, fantasy, family, ghibli",
                "description": "Sisters moving to the countryside befriend gentle forest spirits alongside their mother’s recovery.",
                "insights": "A gentle, heartwarming tribute to childhood wonder and nature, Totoro remains Studio Ghibli’s most beloved and culturally iconic creation.",
                "director": "Hayao Miyazaki",
                "duration": "86 min"

                },

                {
                    "id": 82,
                    "title": "Perfect Blue",
                    "year": "1997",
                    "rating": "8.24",
                    "image": "https://i.pinimg.com/736x/ea/41/95/ea4195427d7ccae9643e1d2c46e64d1f.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/9d/d3/da/9dd3daa64c08ebb62de412b8858ed9af.jpg",
                    "category": "psychological, thriller, drama, award, featured",
                "description": "A pop idol’s life spirals into terror after she leaves her group, as stalking and blurred reality threaten her sanity.",
                "insights": "A dark, meticulously crafted psychological thriller by Satoshi Kon that unnerves and hypnotizes—widely regarded as a genre-defining masterpiece.",
                "director": "Satoshi Kon",
                "duration": "81 min"
                },

                {
                    "id": 83,
                    "title": "Wolf Children",
                    "year": "2012",
                    "rating": "8.53",
                    "image": "https://i.pinimg.com/1200x/ec/fe/7e/ecfe7e2257b849059b8bbaf48bfe743a.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/b3/5c/25/b35c25b73939e6283cccaadb4f9615bb.jpg",
                    "category": "fantasy, slice‑of‑life, drama, award, featured",
                "description": "A young woman raises her half‑wolf children alone while protecting their secret identity.",
                "insights": "A tender, poignant exploration of motherly love, identity, and acceptance—Chambliss’s storytelling is emotional and beautifully animated.",
                "director": "Mamoru Hosoda",
                "duration": "117 min"
                },

                {
                    "id": 84,
                    "title": "Suzume",
                    "year": "2022",
                    "rating": "7.0",
                    "image": "https://i.pinimg.com/736x/ff/7a/6d/ff7a6deccfc9faa64f1370c013e1692f.jpg",
                    "modalImage": "https://i.pinimg.com/736x/68/8b/10/688b106b56fca3722ffb9c5b0764599a.jpg",
                    "category": "fantasy, adventure, drama, new, featured",
                "description": "A teenage girl helps close magical doors causing disasters across Japan, forming deep bonds through her journey.",
                "insights": "Makoto Shinkai’s emotional tornado after Your Name and Weathering, Suzume blends shrine lore, magical realism, and heartfelt storytelling—earning Film of the Year at the 2023 Crunchyroll Anime Awards",
                "director": "Makoto Shinkai",
                "duration": "121 min"
                },

                {
                    "id": 85,
                    "title": "The First Slam Dunk",
                    "year": "2022",
                    "rating": "7.7",
                    "image": "https://i.pinimg.com/736x/b0/4f/3b/b04f3bb789bdb7590c3f1cf5491bbc72.jpg",
                    "modalImage": "https://i.pinimg.com/736x/77/72/24/7772245d5ead349cc5c2cbcb0d5133e2.jpg",
                    "category": "sports, basketball, drama, new",
                "description": "A reimagined film retelling of iconic basketball team Shohoku’s rise during high school championship run.",
                "insights": "A love letter to a generation of Slam Dunk fans—this film revives classic energy and nostalgia with polished animation. It won Best Animated Feature–Film at the Japan Academy Awards",
                "director": "Takehiko Inoue",
                "duration": "124 min"
                },

                {
                    "id": 86,
                    "title": "Demon Slayer: Kimetsu no Yaiba – The Movie: Mugen Train",
                    "year": "2020",
                    "rating": "8.58",
                    "image": "https://i.pinimg.com/1200x/7a/c5/c7/7ac5c7af01917b0d06147f5cb8d55fd3.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/26/aa/11/26aa11a2cea6529ed1823d5e196ecb75.jpg",
                    "category": "action, fantasy, dark fantasy, supernatural, new, award",
                "description": "Following the events of the first season, Tanjiro and the Demon Slayer Corps ride the Mugen Train to investigate a series of disappearances linked to a powerful Lower Rank demon.",
                "insights": "This film seamlessly continues the TV series’ emotional intensity and breathtaking Ufotable animation, delivering one of the most poignant arcs in the franchise while breaking box‑office records worldwide.",
                "director": "Haruo Sotozaki",
                "duration": "119 minutes"
                },

                {
                    "id": 87,
                    "title": "Belle",
                    "year": "2021",
                    "rating": "8.12",
                    "image": "https://i.pinimg.com/1200x/d5/0b/c3/d50bc303ab4690bed68ce46d71dea3bf.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/08/9b/5e/089b5ea075ac19a0b87aeda46f83f1cf.jpg",
                    "category": "fantasy, drama, music, science fiction, award, new",
                "description": "In the digital world ‘U,’ shy high‑schooler Suzu takes on the avatar ‘Belle’ and becomes a global singing sensation, leading her to confront both online and real‑world demons.",
                "insights": "Hosoda’s stunning fusion of fairy‑tale motifs and social media commentary showcases the power of music and virtual connection, anchored by a deeply empathetic heroine.",
                "director": "Mamoru Hosoda",
                "duration": "121 minutes"
                },

                {
                    "id": 88,
                    "title": "Akira",
                    "year": "1988",
                    "rating": "8.16",
                    "image": "https://i.pinimg.com/1200x/75/26/06/7526061323f0d95b1b016e9df7b87cc1.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/a9/d3/0f/a9d30f975fd6333d9f16ff9854cb2874.jpg",
                    "category": "Seinen, movie, sci-fi, cyberpunk, action, featured",
                "description": "In a dystopian Neo‑Tokyo, a biker gang member tries to rescue his friend after government experiments awaken destructive psychic powers.",
                "insights": "Akira is a landmark in cyberpunk anime—visually stunning and energetically paced, its kinetic animation remains influential. While its dense storyline and limited character development divide some viewers, many praise its ‘phenomenal animation and sheer kinetic energy’ :contentReference[oaicite:0]{index=0}, and one Redditor called it “an essential anime film",
                "director": "Katsuhiro Otomo",
                "duration": "124 minutes"
                },

                {
                    "id": 89,
                    "title": "Your Name",
                    "year": "2016",
                    "rating": "8.83",
                    "image": "https://i.pinimg.com/736x/a7/11/fb/a711fb8cc118d03a861d915895e48f24.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/af/b8/eb/afb8eb8ab544f5d89ace669f7e05f26f.jpg",
                    "category": "fantasy, romance, drama, supernatural, featured, award",
                "description": "Two high‑schoolers mysteriously swap bodies and must locate each other before disaster strikes, weaving romance across time and space.",
                "insights": "A visual and emotional masterpiece by Makoto Shinkai, Your Name blends superb animation with a heartfelt story about connection, memory, and destiny. It became the highest‑grossing anime film worldwide and holds a 98% critics score on Rotten Tomatoes",
                "director": "Makoto Shinkai",
                "duration": "106 min"
                },
                {
                    "id": 90,
                    "title": "Ghost in the Shell",
                    "year": "1995",
                    "rating": "8.00",
                    "image": "https://i.pinimg.com/1200x/ac/6f/09/ac6f093cebbdb63caa9f9dd93282f061.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/88/8a/14/888a145993841fc21ede3624be256bbd.jpg",
                    "category": "sci‑fi, cyberpunk, action, philosophical, featured",
                "description": "In a near‑future Japan, cyborg Major Motoko Kusanagi hunts the Puppet Master, a hacker who can rewrite human minds, leading to existential questions of identity.",
                "insights": "Oshii’s landmark film blends noir‑style storytelling, haunting Kenji Kawai music, and pioneering animation to explore consciousness and the limits of humanity in a technologically advanced world. Its thematic depth and visual innovation have influenced countless works in both anime and live‑action sci‑fi.",
                "director": "Mamoru Oshii",
                "duration": "83 minutes"
                },

                {
                    "id": 91,
                    "title": "The Boy and the Heron",
                    "year": "2023",
                    "rating": "7.70",
                    "image": "https://i.pinimg.com/736x/45/60/f2/4560f2ff127153755bf675cd721aef99.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/a3/1a/6f/a31a6fa6d29b63572340fc324addf64a.jpg",
                    "category": "fantasy, adventure, drama, ghibli, award, new",
                "description": "After losing his mother in wartime, young Mahito moves to his aunt’s estate and follows a mysterious gray heron into a world between life and death, embarking on a journey of wonder and self‑discovery.",
                "insights": "Miyazaki’s presumed swan song weaves personal history with surreal adventure, combining Studio Ghibli’s hand‑drawn artistry and Joe Hisaishi’s emotive score. It meditates on grief, curiosity, and the transition from childhood to adulthood with profound lyrical beauty.",
                "director": "Hayao Miyazaki",
                "duration": "124 minutes"
                },
                {
                    "id": 92,
                    "title": "The Tale of the Princess Kaguya",
                    "year": "2013",
                    "rating": "8.21",
                    "image": "https://i.pinimg.com/736x/3b/64/a8/3b64a83021a0af69bf5af853b5b5af5f.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/89/18/2b/89182bc4bbc900fa256f917d09b554cf.jpg",
                    "category": "fantasy, historical, drama, ghibli, award",
                "description": "A baby plucked from bamboo grows into Princess Kaguya, whose radiant beauty forces her father to seek suitors—only for her to yearn for a simpler life.",
                "insights": "Isao Takahata’s hand‑drawn masterpiece melds ethereal water‑colour visuals with a timeless folktale, exploring fate, desire, and the price of beauty in a deeply lyrical fashion.",
                "director": "Isao Takahata",
                "duration": "137 minutes"
                },
                {
                    "id": 93,
                    "title": "Dragon Ball Super: Super Hero",
                    "year": "2022",
                    "rating": "7.1",
                    "image": "https://i.pinimg.com/736x/32/0f/7f/320f7f47ebcd269bb423db6448f6f5af.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/c4/45/16/c44516e0dcb43dcd8cc48f9581e333f4.jpg",
                    "category": "action, adventure, fantasy, superhero, new",
                "description": "The Red Ribbon Army resurfaces with new androids Gamma 1 & 2—Piccolo and Gohan must step up as Goku’s absence leaves a world in peril.",
                "insights": "Tetsuro Kodama reinvigorates the franchise with fresh CGI‑driven fights and emotional stakes, spotlighting two underused heroes in a fast‑paced, fun-packed outing.",
                "director": "Tetsuro Kodama",
                "duration": "100 minutes"
                },

                {
                    "id": 94,
                    "title": "Spy × Family Code: White",
                    "year": "2023",
                    "rating": "94%",
                    "image": "https://i.pinimg.com/736x/fd/27/fd/fd27fda8be20687fa3387f0801c5a175.jpg",
                    "modalImage": "https://i.pinimg.com/736x/92/ff/22/92ff22ce85f7022e38144970f7ba001f.jpg",
                    "category": "action, comedy, slice‑of‑life, spy, new",
                "description": "Loid’s ‘perfect family’ takes a winter getaway—only for Anya’s mischief to trigger a high‑stakes military plot that could unravel world peace.",
                "insights": "Takashi Katagiri amplifies the series’ charm into a globe‑trotting caper, blending crisp Wit/CloverWorks animation with humor, heart, and surprisingly intense action beats.",
                "director": "Takashi Katagiri",
                "duration": "110 minutes"
                },

                {
                    "id": 95,
                    "title": "Spider‑Man: Into the Spider‑Verse",
                    "year": "2018",
                    "rating": "8.4",
                    "image": "https://i.pinimg.com/1200x/94/8d/bb/948dbb27e6301e61c5f0532b9eb04db6.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/92/65/b9/9265b941d72452b82687ddb571cde593.jpg",
                    "category": "action, adventure, superhero, animation",
                "description": "Teenager Miles Morales gains powers and joins a team of Spider‑People from alternate dimensions to stop the Kingpin’s multiverse‑shattering plan.",
                "insights": "Directed by Persichetti, Ramsey & Rothman, this innovative film’s multilayered animation style and heartfelt story broke the mold, earning both critical and audience acclaim.",
                "director": "Bob Persichetti, Peter Ramsey, Rodney Rothman",
                "duration": "117 minutes"
                },
                {
                    "id": 96,
                    "title": "One Piece Film: Red",
                    "year": "2022",
                    "rating": "8.00",
                    "image": "https://i.pinimg.com/1200x/f6/3d/32/f63d32144329e201f804f073952a5afb.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/f3/55/f2/f355f250e25e7354a90b2afc79a2ddad.jpg",
                    "category": "action, adventure, fantasy, musical, new",
                "description": "Straw Hat Pirates get invited to a concert by Uta—the world’s most beloved singer and Luffy’s long‑lost daughter—only to uncover deep conspiracies behind her fame.",
                "insights": "Taniguchi’s vibrant direction and Nakata’s catchy score deliver a fresh, musical twist to the franchise, delighting both long‑time fans and newcomers alike.",
                "director": "Gorō Taniguchi",
                "duration": "115 minutes"
                },
                {
                    "id": 97,
                    "title": "A Whisker Away",
                    "year": "2020",
                    "rating": "7.05",
                    "image": "https://i.pinimg.com/1200x/19/6d/6e/196d6e7f82a7920f260a6a6f266f3222.jpg",
                    "modalImage": "https://i.pinimg.com/736x/a3/b7/4d/a3b74d8f5336cf5a6f9288027cf7d433.jpg",
                    "category": "romance, fantasy, supernatural, new",
                "description": "Miyo Sasaki uses a magical cat mask to transform into a feline ‘Tarō’ and get closer to her crush—only to discover the price of hiding behind another form.",
                "insights": "Combining Netflix’s widescreen canvas with Sato and Shibayama’s delicate direction, the film explores young love and identity through whimsical yet poignant storytelling.",
                "director": "Junichi Sato, Tomotaka Shibayama",
                "duration": "104 minutes"
                },

                {
                    "id": 98,
                    "title": "Jujutsu Kaisen 0",
                    "year": "2021",
                    "rating": "8.50",
                    "image": "https://i.pinimg.com/1200x/fd/37/cd/fd37cdadeea6cf97ca6acec593fcff2b.jpg",
                    "modalImage": "https://i.pinimg.com/736x/62/61/3c/62613c754cd47d09094af20d79d919a9.jpg",
                    "category": "dark fantasy, action, supernatural, new",
                "description": "Prologue to the series: Yuta Okkotsu strains under a deadly curse and enrolls at Tokyo Jujutsu High to control Rika’s spirit and confront past trauma.",
                "insights": "MAPPA elevates the origin story with kinetic fight choreography and emotional depth, setting a high bar for anime film adaptations of manga arcs.",
                "director": "Sunghoo Park",
                "duration": "105 minutes"
                },
                {
                    "id": 99,
                    "title": "To Every You I've Loved Before",
                    "year": "2022",
                    "rating": "7.35",
                    "image": "https://i.pinimg.com/1200x/b3/36/e3/b336e344ebc37eb5f1a5068bc66b934a.jpg",
                    "modalImage": "https://i.pinimg.com/736x/82/78/ee/8278eeec27ae1394f5be6bcff3ac6565.jpg",
                    "category": "romance, fantasy, drama",
                "description": "Koyomi Takasaki meets Kazune Takigawa from a parallel world where they are lovers—sparking a journey through alternate realities and first loves.",
                "insights": "This thoughtful romance uses sci‑fi trappings to probe the nature of choice and destiny, balancing heartfelt moments with speculative intrigue.",
                "director": "Jun Matsumoto",
                "duration": "102 minutes"
                },
                {
                    "id": 100,
                    "title": "Sword Art Online the Movie: Ordinal Scale",
                    "year": "2017",
                    "rating": "9.2",
                    "image": "https://i.pinimg.com/1200x/10/d5/35/10d5351e46cbde277b9b7d31b2d2b405.jpg",
                    "modalImage": "https://i.pinimg.com/1200x/95/d0/9b/95d09b86f705c36ad28092b9a70b2f3f.jpg",
                    "category": "action, sci‑fi, fantasy, adventure, romance",
                "description": "In 2026, four years after the SAO incident, a new AR system called the Augma thrusts Kirito and friends into ‘Ordinal Scale’—but the game hides a dark secret.",
                "insights": "This film captures the series’ signature emotional highs and Ufotable’s trademark kinetic action, weaving a fresh tale that bridges seasons while pushing the technology theme forward in a compelling way.",
                "director": "Tomohiko Itō",
                "duration": "120 minutes"
                },

                {
                        "id": 101,
                        "title": "A Silent Voice",
                        "year": "2016",
                        "rating": "9.02",
                        "image": "https://i.pinimg.com/1200x/93/95/d4/9395d445ecbd3f13094ae8b10c0b3aeb.jpg",
                        "modalImage": "https://i.pinimg.com/1200x/82/7f/f9/827ff9cd3db798ee43ee68dcca56cf29.jpg",
                        "category": "drama,school,psychological,romance,featured",
                        "description": "A former bully seeks redemption by befriending the deaf girl he once tormented.",
                        "insights": "A profoundly human story tackling bullying, guilt, and healing with elegance and depth. Praised for its thoughtful direction and emotional weight, it holds a 95% critics and 94% audience score on Rotten Tomatoes :contentReference[oaicite:3]{index=3}.",
                        "director": "Naoko Yamada",
                        "duration": "129 min"
                    }
                ]

                for movie in movies_data:
                    cursor.execute('''
                                INSERT INTO movies (id, title, year, rating, image, modalImage, category, description, insights, director, duration)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                        movie['id'],
                        movie['title'],
                        movie['year'],
                        movie['rating'],
                        movie['image'],
                        movie['modalImage'],
                        movie['category'],
                        movie['description'],
                        movie['insights'],
                        movie['director'],
                        movie['duration']
                    ))
                db.commit()

        # ... rest of the existing code ...

        # Add endpoint to fetch movie data
        @app.route('/api/movies')
        def get_movies():
            try:
                db = get_db()
                cursor = db.cursor()
                cursor.execute('SELECT * FROM movies')
                movies_list = [dict(row) for row in cursor.fetchall()]
                return jsonify(movies_list)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    # Add this endpoint to fetch anime data
    @app.route('/api/anime')
    def get_anime():
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('SELECT * FROM anime')
            anime_list = [dict(row) for row in cursor.fetchall()]
            return jsonify(anime_list)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

# Initialize the database
init_db()


@app.route('/')
def index():
    """Landing page for WatchBuddy"""
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, password FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = username
            return redirect(url_for('anime'))
        else:
            error = "Invalid username or password"
            return render_template('login.html', error=error)

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration page"""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match")

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                           (username, email, hashed_password))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('signup.html', error="Username or email already exists")

    return render_template('signup.html')


@app.route('/anime')
def anime():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('anime.html', username=session['username'], active_page='anime')


@app.route('/movies')
def movies():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('movies.html', username=session['username'], active_page='movies')


@app.route('/genres')
def genres():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('genres.html', username=session['username'], active_page='genres')


@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', username=session['username'], active_page='chat')


@app.route('/trending')
def trending():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('trending.html', username=session['username'], active_page='trending')


@app.route('/watchlist')
def watchlist():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('watchlist.html', username=session['username'], active_page='watchlist')


@app.route('/logout')
def logout():
    """Logout user"""
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('index'))


@app.route('/chatbot', methods=['POST'])
def chatbot():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    message = data.get('message', '').strip().lower()

    if not message:
        return jsonify({"response": "Please type something so I can help you!"})

    db = get_db()
    cursor = db.cursor()

    try:
        # Handle greetings
        if any(word in message for word in ['hello', 'hi', 'hey', 'greetings']):
            return jsonify(
                {"response": "👋 Hello! I'm ChatBuddy, your anime and movie assistant. How can I help you today?"})

        # Handle title search without keywords
        found_title = None

        # Search in anime table
        cursor.execute("SELECT * FROM anime WHERE LOWER(title) LIKE ? LIMIT 1", (f'%{message}%',))
        result = cursor.fetchone()

        # If not found in anime, search in movies
        if not result:
            cursor.execute("SELECT * FROM movies WHERE LOWER(title) LIKE ? LIMIT 1", (f'%{message}%',))
            result = cursor.fetchone()

        if result:
            found_title = result['title']
            response = f"🎥 Here's information about <strong>{result['title']}</strong>:\n\n"
            response += f"📅 Year: {result['year']}\n"
            response += f"⭐ Rating: {result['rating']}\n"
            response += f"📝 Description: {result['description']}\n"
            if 'insights' in result:
                response += f"\n💡 Insights: {result['insights']}\n"
            return jsonify({"response": response, "type": "info", "item": dict(result)})

        # Handle recommendations
        elif any(word in message for word in ['recommend', 'suggest', 'what to watch']):
            # Check for genre specification
            genres = ['action', 'fantasy', 'romance', 'comedy', 'drama', 'sci-fi', 'horror', 'shonen', 'seinen',
                      'shojo']
            genre = next((g for g in genres if g in message), None)

            # Check for type specification
            media_type = 'anime' if 'anime' in message else 'movie' if 'movie' in message else None

            # Build query based on parameters
            query = "SELECT title, year, rating, description, image FROM "
            where_clause = []
            params = []

            if media_type == 'anime':
                query += "anime"
            elif media_type == 'movie':
                query += "movies"
            else:
                # Default to anime if no type specified
                query += "anime"
                media_type = 'anime'

            if genre:
                where_clause.append("category LIKE ?")
                params.append(f'%{genre}%')

            if where_clause:
                query += " WHERE " + " AND ".join(where_clause)

            query += " ORDER BY RANDOM() LIMIT 3"

            cursor.execute(query, params)
            results = cursor.fetchall()

            if not results:
                return jsonify({"response": "I couldn't find any recommendations. Try being more specific!"})

            response = "🎬 Here are some recommendations for you:\n"
            for item in results:
                response += f"\n- <strong>{item['title']}</strong> ({item['year']}) ⭐ {item['rating']}\n{item['description']}\n"

            return jsonify({"response": response, "type": "recommendations", "results": [dict(row) for row in results]})


        # Handle watchlist viewing
        elif any(word in message for word in ['show watchlist', 'my watchlist', 'whats in my watchlist']):
            cursor.execute('''
                SELECT id, title, year, rating, image 
                FROM watchlist 
                WHERE user_id = ?
                ORDER BY added_at DESC
            ''', (session['user_id'],))

            watchlist = cursor.fetchall()

            if not watchlist:
                return jsonify({"response": "Your watchlist is empty. Add some anime or movies to get started!"})

            response = "📋 Here's your watchlist:\n\n"
            for item in watchlist:
                response += f"- <strong>{item['title']}</strong> ({item['year']}) ⭐ {item['rating']}\n"

            return jsonify({"response": response, "type": "watchlist", "items": [dict(row) for row in watchlist]})

        # Handle unknown requests
        else:
            return jsonify({
                               "response": "I'm here to help you with anime and movie recommendations and information! Try asking about a specific title or asking for recommendations."})

    except Exception as e:
        print(f"Chatbot error: {str(e)}")
        return jsonify({"response": "Sorry, I encountered an error. Please try again later."}), 500
# Watchlist API Endpoints
@app.route('/add_to_watchlist', methods=['POST'])
def add_to_watchlist():
    """Add anime to user's watchlist"""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    data = request.get_json()
    anime_id = data.get('anime_id')
    title = data.get('title')

    if not anime_id or not title:
        return jsonify(success=False, error="Missing required data"), 400

    year = data.get('year', '')
    rating = data.get('rating', '')
    image = data.get('image', '')

    try:
        db = get_db()
        cursor = db.cursor()

        # Check if already in watchlist
        cursor.execute('''
            SELECT id FROM watchlist 
            WHERE user_id = ? AND anime_id = ?
        ''', (session['user_id'], anime_id))
        existing = cursor.fetchone()

        if existing:
            return jsonify(success=False, error="Already in watchlist"), 409

        # Add to watchlist
        cursor.execute('''
            INSERT INTO watchlist (user_id, anime_id, title, year, rating, image)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], anime_id, title, year, rating, image))
        db.commit()
        return jsonify(success=True)
    except sqlite3.IntegrityError:
        return jsonify(success=False, error="Database error"), 500
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route('/remove_from_watchlist/<int:item_id>', methods=['DELETE'])
def remove_from_watchlist(item_id):
    """Remove item from watchlist"""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            DELETE FROM watchlist 
            WHERE id = ? AND user_id = ?
        ''', (item_id, session['user_id']))

        if cursor.rowcount == 0:
            return jsonify(success=False, error="Item not found"), 404

        db.commit()
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route('/get_watchlist')
def get_watchlist():
    """Get user's watchlist"""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT id, anime_id, title, year, rating, image 
            FROM watchlist 
            WHERE user_id = ?
            ORDER BY added_at DESC
        ''', (session['user_id'],))

        watchlist = [dict(row) for row in cursor.fetchall()]
        return jsonify(watchlist)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

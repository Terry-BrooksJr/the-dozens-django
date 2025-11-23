
-- CREATE FUNCTION TO GENERATE INSULT REFERENCE ID 
CREATE OR REPLACE FUNCTION create_reference_id_base64(primary_key text)
RETURNS text
LANGUAGE plpgsql
VOLATILE
AS '
DECLARE
  prefixes text[] := ARRAY[''GIGGLE'',''CHUCKLE'',''SNORT'',''SNICKER'',''CACKLE''];
  idx int;
  b64 text;
BEGIN
  -- Pick a random prefix
  idx := floor(random() * array_length(prefixes, 1))::int + 1;

  -- Convert to Base32 (Postgres "base32" encoding is RFC 4648 with padding)
  b64 := encode(convert_to(primary_key, ''UTF8''), ''base64'');

  RETURN prefixes[idx] || ''_'' || b64;
END;
';
-- CREATE TRIGGER TO CALL FUNCTION ON INSERT OF NEW RECORDS INTO INSULT TABLE

CREATE OR REPLACE FUNCTION trg_set_reference_id_base64()
RETURNS trigger
LANGUAGE plpgsql
AS '
BEGIN
  IF NEW.reference_id IS NULL THEN
    NEW.reference_id := create_reference_id_base64(NEW.insult_id::text);
  END IF;
  RETURN NEW;
END;
';

DROP TRIGGER IF EXISTS set_reference_id_on_insert ON public.insults;
CREATE TRIGGER set_reference_id_on_insert
BEFORE INSERT ON public.insults
FOR EACH ROW
EXECUTE FUNCTION trg_set_reference_id_base64();

DELETE FROM insults;
DELETE FROM insult_categories;
DELETE FROM themes;

-- Seed/refresh insult categories with descriptions
-- Requires Postgres. Safe to re-run due to ON CONFLICT upsert.

-- Insert consolidated categories
INSERT INTO themes (theme_key, theme_name, description) VALUES ('AGE', 'Age & Time', 'Insults focused on age, lifespan, or references to time (e.g., being old, outdated).');
INSERT INTO themes (theme_key, theme_name, description) VALUES ('APP', 'Appearance & Body', 'Insults about physical traits such as weight, height, attractiveness, or body features.');
INSERT INTO themes (theme_key, theme_name, description) VALUES ('INT', 'Intelligence & Wit', 'Insults targeting intellect, cleverness, or lack of common sense.');
INSERT INTO themes (theme_key, theme_name, description) VALUES ('WTH', 'Wealth & Status', 'Insults referencing financial standing, possessions, or class.');
INSERT INTO themes (theme_key, theme_name, description) VALUES ('BEH', 'Behavior & Habits', 'Insults about work ethic, lifestyle, rudeness, or gross behavior.');
INSERT INTO themes (theme_key, theme_name, description) VALUES ('REL', 'Relationships & Roles', 'Insults based on family roles or relationships (e.g., parental jokes).');
INSERT INTO themes (theme_key, theme_name, description) VALUES ('ONE', 'One-Off / Situational', 'Unique or pop-culture-specific insults that don’t fit other categories.');
INSERT INTO themes (theme_key, theme_name, description) VALUES ('INTL', 'Internal (Ignore)', 'Reserved for internal testing, QA, or non-production seed data.');


INSERT INTO insult_categories (category_key, name, description, theme_id) VALUES
  -- Daddy variants
  ('DO',   'daddy - old',    'Insults aimed at a father figure’s age or being past one’s prime.', 'AGE'),
  ('DS',   'daddy - stupid', 'Insults aimed at a father figure’s intellect or clueless behavior.', 'INT'),

  -- Core traits
  ('F',    'fat',            'Body-size jokes focused on largeness, heft, or weight.','APP'),
  ('H',    'hairy',          'Jokes about excessive or unusual body hair.', 'APP'),
  ('L',    'lazy',           'Themes of idleness, avoidance of work, or minimal effort.', 'BEH'),
  ('N',    'nasty',          'Gross-out humor: dirtiness, foul habits, or general grime vibes.', 'BEH'),
  ('O',    'old',            'Age-related jokes: ancient, outdated, dusty, fossil-adjacent.', 'AGE'),
  ('P',    'poor',           'Money/means jokes: thrift, scarcity, or creative penny-pinching.', 'WTH'),
  ('SRT', 'Short', 'Height jokes about being unusually small, undersized, or comically tiny.', 'APP'),
  ('SKN',  'skinny',         'Body-size jokes focused on thinness or scrawniness.', 'APP'),
  ('S',    'stupid',         'General intellect/logic fails, cluelessness, or silly errors.', 'INT'),
  ('T',    'tall',           'Height gags about towering stature or being comically elongated.', 'APP'),
  ('U',    'ugly',           'Looks/appearance jokes about being hard on the eyes.', 'APP'),

  -- Special / internal
  ('SNWF', 'one-off',        'Miscellaneous jokes that don’t neatly fit other categories.', 'ONE'),
  ('TEST', 'INTERNAL - TEST','Reserved for QA and non-production seeding; exclude from public APIs.', 'INTL')
ON CONFLICT (category_key)
DO UPDATE SET
  name        = EXCLUDED.name,
  description = EXCLUDED.description;

-- Clear Current Jokes to Avoid Duplication
-- Clear Current Jokes to Avoid Duplication


-- Insert insults (no id/reference_id/added_on; added_by_id=1)
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo daddy so old, his Social Security number is 4.', NOW(), FALSE, 'A', 1, 'DO', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo daddy is so dumb he turned down a blowjob because he thought it would mess up his unemployment check.', NOW(), TRUE, 'A', 1, 'DS', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo daddy so dumb, somebody said it was chilly outside so he went to get a bowl.', NOW(), TRUE, 'A', 1, 'DS', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so stupid that she thought Star Wars was a war for stars.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so stupid, when they said ''Order in the court'', she asked for fries and a shake.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she trips over the wireless internet.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb she called me to ask for my phone number.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb when your dad said it was chilly outside, she ran outside with a spoon.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so stupid, she couldn’t read an audiobook.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she got locked in Furniture World and slept on the floor.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she worked at a M&M factory and threw out all the W''s.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she put a watch in a piggybank and said she was saving time.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she can''t pass a blood test.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she sits on the floor and watches the couch.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she ordered a cheeseburger without the cheese.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb she thought a quarterback was a refund.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb she cooks her own complimentary breakfast.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so stupid when thieves broke into her house and stole the TV, she chased after them shouting ''Wait! You forgot the remote!''', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she went to the library to find Facebook.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama’s so stupid she thought fortnite was fork night.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she cooked her own complimentary breakfast.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she tried to eat Eminem the rapper.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... when they said that it is chilly outside, she went outside with a bowl and a spoon.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she puts lipstick on her forehead to make-up her mind.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she thought KFC was UFC for chickens.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she failed a survey.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so stupid she thought light sabers had less calories.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... that she burned down the house with a CD burner.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so stupid, she sold the house to pay the mortgage.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she got lost in a telephone booth.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she stopped at a stop sign and waited for it to turn green.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... it took her 2 hours to watch 60 seconds.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, when she heard about cookies on the Internet, she ate her computer.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she stole free bread.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb she sold her car to get gasoline money!', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so stupid, she went to the dentist to get Bluetooth.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so stupid, she got locked in a mattress store and slept on the floor.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so stupid, she studied for a Covid test.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb when you stand next to her you hear the ocean!', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she got fired from the M &amp; M factory for throwing away all the W’s.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she tried to commit suicide by jumping out the basement window.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so stupid, she took a ruler to bed to see how long she slept.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, it takes her an hour to cook minute rice.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, when the doctor told her she had coronavirus, she bought a new laptop.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she got locked in a grocery store and starved.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... when she asked me what kind of jeans am I wearing I said, ''Guess'', and she said, ''Levis''.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('“Yo mama’s so stupid she told me to meet her at the corner of Walk and Don’t Walk.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she sold her car for gas money.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so stupid, she returned a doughnut because it had a hole in it.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so stupid... she put lipstick on her forehead to make up her mind.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she put sugar on the bed because she wanted sweet dreams.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb that she spent hours starting at a glass of orange juice because it said ''concentrate'' on the package.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb it takes her twenty minutes to cook minute rice.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb that she thought, Dunkin'' Donuts was a basketball team!', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she tried to eat Eminem!', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so dumb, she thought Twitter was social media for birds.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so stupid, she climbed over a glass wall to see what was on the other side.', NOW(), TRUE, 'A', 1, 'S', 'INT', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she bungee jumps she goes straight to hell!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, she left in high heels and came back in flip flops.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat she can’t reach her back pocket.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she gets on the elevator it says, ''cNext stop, Hell''d!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when you go around her you get lost!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, she wakes up on both sides of the bed.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she took her shirt off at the strip club, everyone thought she was Jabber the Hut from Star Wars.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she went bungee jumping in a yellow dress, everyone was screaming the suns falling!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, she goes to the car wash to take showers.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, a picture of her would fall off the wall!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat she needs two watches for two different time zones.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, if she got her shoes shined, she’d have to take his word for it!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, she fell in love</a> and broke it.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she has wants someone to shake her hand, she has to give directions!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, she left in high heels and came back in flip flops.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she jumps up in the air she gets stuck!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she has more chins than a Chinese phone book.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, she gets group insurance!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... it took me a bus and two trains just to get on her good side.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, when she got hit by a bus she asked, “Who threw that rock?”', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so big, when she talks to herself it’s a long-distance call.', NOW(), FALSE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, when she walked past the TV, I missed three episodes.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when a bus hit her she said, ''Who threw the pebble?''', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, that when she hauls ass it takes her two trips.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat when she goes camping, the bears hide their food.', NOW(), FALSE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she uses an air balloon for a parachute.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she takes a bath she fills the tub then turns on the water.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama is so fat she poured two drops of water into the tub and got it. It still overflowed.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she wears a red dress all the kids scream look it''9s the Kool-Aid man.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, when she crossed the road people mistook her for a roundabout.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she had to be baptized at sea world.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she eats Wheat Thicks.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... you could use her bellybutton as a wishing well.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... that she needs a bookmark to keep track of all her chin rolls!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, and old, that when God said ''Let there be light,'' he was just asking her to move out of the way.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... the back of her neck is like a pack of hot dogs!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, her job title is Spoon and Fork Operator!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she put on her lipstick with a paint roller.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... whenever she goes to the beach the tide comes in!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... the last time she saw 90210 was on the scale!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she broke a branch in her family tree!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she steps on the scale it says we don''t do livestock.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when God said, ''cLet there be light,''d he had to ask her to move out of the way.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she had her ears pierced by harpoon.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, when stepped on the scale it said, ‘To be continued.’', NOW(), FALSE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... they had to install speed bumps at all you can eat buffets.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, when she skips a meal, the whole stock market drops.', NOW(), FALSE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... that when she wanted a waterbed, they had to put a cover over the Atlantic Ocean.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she''s got to wake up in sections.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she went to the movies and sat next to everyone.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she looks like she''s smuggling an SUV!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat when she tripped over on 4th Ave, she landed on 12th.', NOW(), FALSE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so fat that even Dora don''t have time to explore her!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she sat on a tractor and made a pick-up truck.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she jumped off the Grand Canyon and got stuck.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she goes to an amusement park, people try to ride her!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she uses the interstate as a slip and slide.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, Thanos had to clap.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she puts on her yellow rain coat and walks down the street people shout out ''ctaxi''d!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('“Yo mama’s so fat that when she walked past the TV, I missed three episodes.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she sits on the beach, whales swim up to her and sing we are family...!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... her nickname is Lardo.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... every time she walks in high heels, she strikes oil!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat that when she sat on an iPhone it turned into an iPad.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, she uses Google Earth to take a selfie.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she sat on a rainbow and made skittles.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she has seat belts on the chairs to keep her fat from rolling off!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES (' Yo mama so fat when she got on the scale it said, ''I need your weight not your phone number''.', NOW(), FALSE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she lays on the beach and people run around yelling Free Willy!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she wore a blue and green sweater, everyone thought she was Planet Earth.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she jumped in the air and got stuck.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, when she takes a shower, her feet don’t get wet!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... the government forced her to wear taillights and blinkers so no one else would get hurt.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she turns around they throw her a welcome back party.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat that her official job title is spoon and fork operator.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she goes to Taco Bell, they run for the border!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, I took a picture of her last Christmas and the damn thing''s still printing.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she supplies 99% of the world''9s gas.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, when she gets in an elevator, it HAS to go down!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... NASA has to orbit a satellite around her!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so fat that when she walked past the TV I miss three episodes.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, when she buys a fur coat, a whole species goes extinct.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she rolled over 4 quarters and made a dollar!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she goes to a restaurant, looks at the menu, and says, ''okay!''', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, she was floating in the ocean and Spain claimed her for their new world.', NOW(), FALSE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat that when she hauls ass, she has to make two trips!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she rolled out of bed and everybody thought there was an earthquake.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, when God said, “Let there be light,” he asked her to move out of the way.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat that her belt size is ''equator''!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... her measurements are 26-34-28, and her other arm is just as big!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she makes Godzilla look like an action figure.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she was in school she sat next to everybody!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when her beeper goes off, people think she is backing up.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she bungee jumps, she brings down the bridge too.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she walked in front of the TV and I missed 3 shows.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she lays on the beach no one else gets sun!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat that she needs to take our group insurance when she travels.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, she makes Godzilla look like an action figure.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she sank the Titanic!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she dives into the ocean, there is a tsunami-warning!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama’s so fat, when she stepped on the scale it said, ‘To be continued.’', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat she sat on a dollar and when she got up there was 4 quarters.', NOW(), FALSE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she makes a whale look bulimic!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she was floating in the ocean and Spain claimed her for the new world!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she plays hopscotch, she goes North America, Europe, Asia.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat when she tried to weight herself and the scales said ''one at a time please''. ', NOW(), FALSE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat, even Dora can’t explore her.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... people jog around her for exercise.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... when she steps on a scale, it read, ''cone at a time, please''d.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she''s got her own area code!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she was going to Wal-Mart, tripped over Kmart, and landed right on Target!!!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so fat that when she orders a fur coat an entire species goes extinct.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... the highway patrol made her wear ''Caution!, Wide Turn!''', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she needs a watch on both arms because she covers two time zones.', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... her husband has to stand up in bed each morning to see if it''s daylight!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so fat... she fell and made the Grand Canyon!', NOW(), TRUE, 'A', 1, 'F', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so hairy... that Bigfoot tried to take her picture!', NOW(), FALSE, 'A', 1, 'H', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so hairy... she wears a Nike tag on her weave so now everybody calls her Hair Jordan.', NOW(), FALSE, 'A', 1, 'H', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Your mother''s arms are so hairy, when she walks down the street it looks like she has Buckwheat in a headlock.', NOW(), FALSE, 'A', 1, 'H', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so hairy... the zoo offered to buy her kids.', NOW(), FALSE, 'A', 1, 'H', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so hairy... Harry Potter got jealous.', NOW(), FALSE, 'A', 1, 'H', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so hairy... she has cornrows on her back, legs, and feet!', NOW(), FALSE, 'A', 1, 'H', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so hairy... she shaves with a weed-eater.', NOW(), FALSE, 'A', 1, 'H', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so hairy... you almost died of rug burn at birth!', NOW(), FALSE, 'A', 1, 'H', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so hairy people think she’s an Ewok.', NOW(), FALSE, 'A', 1, 'H', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so hairy... her tits look like coconuts.', NOW(), TRUE, 'A', 1, 'H', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so lazy... she starved instead of getting up to get some food.', NOW(), FALSE, 'A', 1, 'L', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so lazy... that she came in last place in a recent snail marathon.', NOW(), FALSE, 'A', 1, 'L', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so lazy... she arrived late at her own funeral.', NOW(), FALSE, 'A', 1, 'L', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so lazy she stands outside to let the wind blow her nose!', NOW(), FALSE, 'A', 1, 'L', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so lazy, she has a stay-at-home job and still is late to work.', NOW(), FALSE, 'A', 1, 'L', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so lazy... she thinks a two-income family is where the man has two jobs.', NOW(), FALSE, 'A', 1, 'L', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so lazy... she''s got a remote control just to operate her remote!', NOW(), FALSE, 'A', 1, 'L', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so lazy, she stuck her nose out the window so the wind could blow it.', NOW(), FALSE, 'A', 1, 'L', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so lazy she woke up from a coma and went to sleep.', NOW(), FALSE, 'A', 1, 'L', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama is nasty. When she went to take a bath, the water jumped out and said, ''That''s okay, I''ll wait.''', NOW(), TRUE, 'A', 1, 'N', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so nasty, she went swimming and made the Dead Sea.', NOW(), FALSE, 'A', 1, 'N', 'BEH',0 );
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama is so nasty she swam the Ink Sea and left a dark streak.', NOW(), TRUE, 'A', 1, 'N', 'BEH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old she still owes Moses a quarter!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... I told her to act her own age, and she died.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... her social security number is 1!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... she knew the Great Wall of China when it was only good!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... she knew Burger King while he was still a prince.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... she ran track with dinosaurs.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so old she has a picture of Abraham carved into her yearbook.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... her birth certificate says expired on it.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... that her bus pass is in hieroglyphics!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... that when she was in school there was no history class.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... she has a picture of Moses in her yearbook.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... her social security number is 1!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so old her driver''s license is written with Roman numerals.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, she walked into an antique store and they kept her.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... her birth certificate is in Roman numerals.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... she was wearing a Jesus starter jacket!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, she walked into an antiques store, and they didn’t let her leave.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... that her bus pass is in hieroglyphics!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, when someone told her to act her age, she died.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so old she took her driving test on a triceratops!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so old her first car was a chariot!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so old she helped write the ten commandments.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... she has a picture of Moses in her yearbook.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so old she cleaned up after the last supper.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... she was wearing a Jesus starter jacket!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... she ran track with dinosaurs.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... her birth certificate is in Roman numerals.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, when she was young, rainbows were still black and white.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, when she was born, the Dead Sea was still just getting sick.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so old she got sold while looking around the antique store!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... she knew the Great Wall of China when it was only good!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, Jurassic Park brings back memories.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... I told her to act her own age, and she died.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, her birth certificate says expired on it.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, she was a waitress at the Last Supper.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... that when she was in school there was no history class.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, she knew Burger King when he was a prince.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... she knew Burger King while he was still a prince.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, her birth certificate is in Roman numerals.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, her driver’s license got hieroglyphics on it!', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so old she knew burger king when he was still a prince.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s so old she still owes Moses money.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so old, when the preacher asked if she knew Jesus, she said, ''Know him? Motherfucker still owes me five dollars.''', NOW(), TRUE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so old... her birth certificate says expired on it.', NOW(), FALSE, 'A', 1, 'O', 'AGE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... she can''t afford to pay attention!', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama house so small, you have to go outside to change your mind.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... I walked in her house and stepped on a cigarette, and your mom said, ''Who turned off the lights?''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... I walked in her house and stepped on a cigarette, and your mom said, ''Who turned off the lights?''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... when I ring the doorbell she says, ''[DING!''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... she was in Walmart with a box of Hefty bags. ''I said, what ya doing?'', She said, ''Buying luggage.''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... the roaches pay the light bill!', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... when I ring the doorbell she says, ''[DING!''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... she waves around a popsicle stick and calls it air conditioning.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... I stepped in her house and I was in the backyard.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... when I saw her kicking a can down the street, I asked her what she was doing, she said, ''Moving''.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... she waves around a popsicle stick and calls it air conditioning.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... when her friend came over to use the bathroom she said, ''Ok, choose a corner.''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... the roaches pay the light bill!', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... when I ring the doorbell she says, ''[DING!''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... she was in Walmart with a box of Hefty bags. ''I said, what ya doing?'', She said, ''Buying luggage.''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... she waves around a popsicle stick and calls it air conditioning.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so poor she can’t even pay attention.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... when I saw her kicking a can down the street, I asked her what she was doing, she said, ''Moving''.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... your family ate cereal with a fork to save milk.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... the roaches pay the light bill!', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... when her friend came over to use the bathroom she said, ''Ok, choose a corner.''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... she was in Walmart with a box of Hefty bags. ''I said, what ya doing?'', She said, ''Buying luggage.''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so poor when I saw her kicking a can down the street, I asked her what she was doing, she said “Moving.”', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... she can''t afford to pay attention!', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... I stepped in her house and I was in the backyard.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so poor, ducks throw bread at her.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... I walked in her house and stepped on a cigarette, and your mom said, ''Who turned off the lights?''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so poor when she goes to the park, ducks throw bread at her!', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... when I saw her kicking a can down the street, I asked her what she was doing, she said, ''Moving''.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... when her friend came over to use the bathroom she said, ''Ok, choose a corner.''', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama house so small that when she orders a large pizza, she has to go outside to eat it.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... I stepped in her house and I was in the backyard.', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so poor... she can''t afford to pay attention!', NOW(), FALSE, 'A', 1, 'P', 'WTH', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short... she has a job as a teller at a piggy bank.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short... she does backflips under the bed.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short ... she poses for trophies!', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short... she can surf on a popsicle stick.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short... she can use a sock for a sleeping bag.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short... she can sit on a dime and swing her legs.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short ... she has to use a ladder to pick up a dime.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short... she has to use rice to roll her hair up.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama’s so short when she plays fortnite she can hide under the freaking store.', NOW(), TRUE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so short, she went to see Santa and he told her to get back to work.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short... she can tie her shoes while standing up.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short... she uses a toothpick as pool stick.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so short ... she can play handball on the curb.', NOW(), FALSE, 'A', 1, 'SRT', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... she can dive through a chain-linked fence.', NOW(), FALSE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... she turned sideways and disappeared.', NOW(), FALSE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... she swallowed a meatball and thought she was pregnant.', NOW(), FALSE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... she can hang glide with a Dorito!', NOW(), FALSE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... she can see through peepholes with both eyes.', NOW(), FALSE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... she don’t get wet when it rains.', NOW(), FALSE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... she uses cotton balls for pillows.', NOW(), FALSE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... she hula hoops with a cheerio.', NOW(), FALSE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... she has to run around in the shower just to get wet.', NOW(), FALSE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... she has to wear a belt with her spandex pants.', NOW(), FALSE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so skinny... her nipples touch.', NOW(), TRUE, 'A', 1, 'SKN', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s feet are so scaly... you can see Crocodile Dundy in her footbath.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so angry, that McDonalds won''t even serve her happy meals.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so clumsy... she got tangled up in a cordless phone.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma ain''t got no ears yelling... Let me hear both sides of the story!', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so chatty, she gave a eulogy at her own funeral.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s house is so small... that when she orders a large pizza she had to go outside to eat it.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma has so many chins... it looks like she''s wearing a fat necklace!', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so grouchy... the McDonald''s she works at doesn''t even serve happy meals.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s house is so small... you have to go outside to change your mind.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s house is so poor... I went to knock on her door and a roach tripped me and a rat took my wallet!', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is cross-eyed and watches TV in stereo.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s glasses are so thick she can look at a map and see people waving.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s mouth is so big... she speaks in surround sound.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s glasses are so thick... that when she looks on a map she can see people waving.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma so confusing even Scooby Doo can''t figure her out!', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama’s teeth are so yellow, when she smiles, she puts the sun out of business.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s middle name is Rambo.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is in a wheelchair and says... ''You ain''t gonna push me around no more!''', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s head is so big... she has to step into her shirts.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s feet are so big... her shoes have to have license plates!', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so nasty... cows with mad cow disease run from her.', NOW(), TRUE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so mean, they don’t give her happy meals at McDonalds.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s nose is so big... that her neck broke from the weight!', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s teeth are so yellow... that when she smiles traffic slows down.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama’s teeth so yellow, when she drinks water, it turns into lemonade.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s teeth are so yellow... that when she smiles everyone sings, ''I got sunshine on a cloudy day''', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s teeth are so yellow... I can''t believe it''s not butter.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so confusing, even Scooby Doo couldn’t solve that mystery.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so scary, even Voldemort won’t say her name.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama’s glasses are so thick, when she looks at a map, she can see people waving at her.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s nose is so big... she makes Pinocchio look like a cat!', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s hair is so short she rolls it with rice.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s head is so big... it shows up on radar.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s glasses are so thick... she can see into the future.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is missing a finger and can''t count past nine.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so clumsy, she makes Humpty Dumpty look like a gymnast.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama''s cooking is so bad even the homeless send it back.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama’s head so big, she dreams in IMAX.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is like the sun... you look at her to long you will go blind!', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s head is so small... she uses a tea bag as a pillow.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so strict, she locked you up in a tower.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so small... that she got her ear pierced and died.', NOW(), FALSE, 'A', 1, 'SNWF', 'ONE', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so tall... she has to take a bath in the ocean.', NOW(), FALSE, 'A', 1, 'T', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so tall... she high-fived God.', NOW(), FALSE, 'A', 1, 'T', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so tall... she tripped over a rock and hit her head on the moon.', NOW(), FALSE, 'A', 1, 'T', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so tall... Shaq looks up to her.', NOW(), FALSE, 'A', 1, 'T', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so tall... she 69''d bigfoot.', NOW(), FALSE, 'A', 1, 'T', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so tall... she can see her home from anywhere.', NOW(), FALSE, 'A', 1, 'T', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so tall... she tripped in Denver and hit her head in New York.', NOW(), FALSE, 'A', 1, 'T', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so tall... she did a cartwheel and kicked the gates of Heaven.', NOW(), FALSE, 'A', 1, 'T', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('TEST - This Document Shoulds be Found by Catagory: ''Test''', NOW(), FALSE, 'A', 1, 'TEST', 'INTL', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('TEST - Document Should Be Found By nsfw: TRUE and Status: ''Deleted''', NOW(), FALSE, 'X', 1, 'TEST', 'INTL', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('TEST - This Document Shoulds be Found by nsfw: true', NOW(), FALSE, 'A', 1, 'TEST', 'INTL', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('TEST - This Document Shoulds be Found by Catagory: ''Test''', NOW(), FALSE, 'A', 1, 'TEST', 'INTL', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... even Rice Krispies won''t talk to her!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... she tried to take a bath and the water jumped out!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, when she walks into the dentist, they make her lay face down.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... she made an onion cry.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... for Halloween she trick-or-treats on the phone!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, she makes blind kids cry.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly that she has to trick or treat over the phone.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... The NHL banned her for life.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... her mom had to tie a steak around her neck to get the dogs to play with her.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... that your father takes her to work with him so that he doesn''t have to kiss her goodbye.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... she turned Medusa to stone!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('“Yo mama’s so ugly she went into a haunted house and they handed her an application.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, she has a sign in her garden saying, ‘Beware of the dog!’', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mo''mma is so ugly... she got beat up by her imaginary friends!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... when she walks down the street in September, people say ''Wow, is it Halloween already?''', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... instead of putting the bungee cord around her ankle, they put it around her neck.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, when she was born the doctor slapped your grandma!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... she gets 364 extra days to dress up for Halloween.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, people dress up as her for Halloween.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, she made an onion cry.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... that she scares blind people!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... when she joined an ugly contest, they said, ''Sorry, no professionals.''', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly that her portraits hang themselves.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, she could scare the moss off a rock!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... when they took her to the beautician it took 12 hours for a quote!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, she turned Medusa to stone.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... just after she was born, her mother said, ''What a treasure!'' And her father said, ''Yes, let''s go bury it!''', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, her birth certificate is an apology letter.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, she made an onion cry.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, her own portraits hang themselves.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma so ugly,  even hello kitty said ''goodbye''!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, she could scare the chrome off a bumper!', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly that the government moved Halloween to be on her birthday.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, her birth certificate is an apology letter from the condom factory.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma''s so ugly, when she was born the doctor slapped her parents.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, she went into a haunted house and the ghosts ran away.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, when she looks in the mirror, her reflection ducks.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... when she walks into a bank, they turn off the surveillance cameras.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... the government moved Halloween to her birthday.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama is so ugly she walked into a haunted house and walked out with a job application.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, even Hello Kitty said goodbye.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo momma is so ugly... they didn''t give her a costume when she tried out for Star Wars.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);
INSERT INTO insults (content,added_on, nsfw, status, added_by_id, category_id, theme_id, reports_count)
VALUES ('Yo mama so ugly, she walked into a Haunted House and walked back out with a job application.', NOW(), TRUE, 'A', 1, 'U', 'APP', 0);

COMMIT;
SELECT * FROM insults; 
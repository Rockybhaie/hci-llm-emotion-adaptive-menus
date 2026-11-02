# Emotion induction: what we do and why

## How the six emotions were chosen

The emotions had to meet three criteria:

1. **Reliable to induce in a lab** with published, validated methods.
2. **Relevant to computer use.** Frustration, boredom and stress are among the states users most often report while working with computers (Baker et al., 2010; Ceaparu et al., 2004).
3. **Distinguishable in the signals.** Each group's two emotions differ clearly in arousal, in valence, or in both. GSR and heart rate mostly track arousal. Valence shows up more in behaviour and self-report.

| Group | Pair | Contrast |
|---|---|---|
| G1 | Stress vs Calm | High vs low arousal, negative vs positive valence |
| G2 | Frustration vs Boredom | High vs low arousal (both negative) |
| G3 | Joy (amusement) vs Sadness | Positive vs negative valence |

Confusion and curiosity were considered and rejected: their inductions are less reliable and harder to standardise.

## The method used for each emotion

Each emotion has an **induction** (about 3 minutes, once at the start of its emotion block), a short **booster** before the second and third sub-block, and, where the literature supports it, an **in-task manipulation** that keeps the state going during the tasks. Films and recall alone fade within minutes (Westermann et al., 1996), and one emotion block now lasts about 14 minutes with three menus in it, so the state is topped up. Task-based manipulations last as long as the task does. **The in-task manipulation applies identically to every sub-block and every menu**; it is implemented once, in the site engine ([MENUS.md](../MENUS.md#induced-faults-menu-independent)).

| Emotion | Before the tasks | During the tasks | Basis |
|---|---|---|---|
| **Stress** | MIST-style mental arithmetic. Single-digit answers. The time limit shrinks 10% after 3 correct answers in a row. A rigged "you vs average" bar always shows the participant below average. "Incorrect" and "Time out" feedback, plus a warning that results will be reviewed | Visible 30 s countdown per task, a "recording performance · compared with others" banner, "slower than most participants" feedback | Montreal Imaging Stress Task (Dedovic et al., 2005); social-evaluative threat as in the TSST (Kirschbaum et al., 1993) |
| **Calm** | 3 min nature video with paced breathing at 6 breaths/min (5 s in, 5 s out) | "There is no rush" instructions, no timer | Stress recovery through nature scenes (Ulrich et al., 1991); slow paced breathing (Lehrer & Gevirtz, 2014) |
| **Frustration** | A goal plus an incentive ("the fastest participants receive a bonus"), because frustration needs a blocked, important goal | Deliberate interface failures: 60% of page loads delayed 2–6 s, 25% of committing menu clicks ignored, the open menu collapsing by itself (20% of navigation attempts, with an equivalent in every menu), "session expired" on Submit (35%, once per task). Every event is logged as `sabotage_*` | Frustrating the user on purpose (Scheirer et al., 2002); causes of user frustration (Ceaparu et al., 2004) |
| **Boredom** | Copying monotonous technical references about concrete for 3 minutes | Every task uses the same dull template ("Find X in Y. What is its item code?") with no feedback | Copying references (van Tilburg & Igou, 2012); repetitive-task induction (Markey et al., 2014); boredom as unengaged attention (Eastwood et al., 2012) |
| **Joy (amusement)** | Wordless comedy clip: *Mr. Bean*, "The Exam" (≈ 5.8 min) | Surprise "Bonus unlocked!" reward with confetti after about 70% of correct answers | Film elicitation (Gross & Levenson, 1995; Schaefer et al., 2010); small unexpected rewards induce positive affect (Isen & Levin, 1972) |
| **Sadness** | Sad film scene: *Taare Zameen Par* (≈ 3.9 min), then 30 s of quiet reflection | None (neutral) | Film elicitation; *The Champ* is the most widely used sadness clip (Gross & Levenson, 1995) |

Film clips and recall are among the most effective induction methods in meta-analyses (Westermann et al., 1996; Lench et al., 2011). We follow the film-elicitation method of Gross and Levenson (1995), but replace their two English-language clips with culturally familiar ones. The amusement clip is wordless, so it works for any participant. The sadness clip is from a film our participants are likely to relate to. The post-induction ratings serve as the manipulation check: happiness should rise after the amusement clip and sadness after the sadness clip, compared with baseline.

## Boosters (before sub-blocks 2 and 3)

A booster is a **30-45 s re-cue** of the same state, shown just before the second and the third menu sub-block of an emotion block. There is none before sub-block 1, because the induction has just run. Boosters reuse the induction activity in a short form (no instructions to read) and are the same for every menu.

| Emotion | Booster | Length |
|---|---|---|
| Stress | One more MIST round (same adaptive time limit and feedback) | 30 s + a 2 s notice |
| Calm | Paced breathing (5 s in, 5 s out) over the nature clips | 40 s |
| Frustration | A reminder of the speed bonus plus a **fixed, unfavourable "current ranking"** (15th of 18 before sub-block 2, 16th of 18 before sub-block 3, about 12 s and 15 s per task behind the leaders), shown for at least 8 s, then Continue (auto-advance at 30 s). The ranking is not real and is explained at the debrief | up to 30 s |
| Boredom | 30 s more of the dull copying task | 30 s |
| Joy | A short amusing clip (`stimuli/videos/boosters/g3_a.mp4`, to be supplied) | up to 35 s |
| Sadness | A short sad clip (`boosters/g3_b.mp4`, to be supplied), then 10 s of quiet reflection | up to 35 s + 10 s |

The two booster clips are not bundled (film scenes are copyrighted; see [stimuli/README.md](../stimuli/README.md)). Until a file is supplied a clearly marked "PLACEHOLDER" screen of the right length is shown, `video_end` is logged with `placeholder: true`, the terminal warns, and `run.py check` lists the clip. The file names are deliberately neutral. Durations come from `config/groups.yaml`.

## Neutral baseline and washout

- **Baseline:** 3 minutes of rest looking at a fixation cross on a mid-grey screen (resting baseline; Jennings et al., 1992). This is the reference for normalising each person's physiological signals (recorded outside this app) and the neutral reference for their mood ratings.
- **Washout:** a neutral clip (about 2.5 min) between the blocks returns the participant towards baseline before the second emotion. A mood rating after it checks that this worked.

## Manipulation checks

After every induction and after every sub-block (every menu), the participant rates:

- **SAM** (Self-Assessment Manikin; Bradley & Lang, 1994): valence, arousal and dominance, each on 9 points.
- **Six emotion items** (stressed, calm, frustrated, bored, happy, sad), each on a 7-point scale. All six are always asked, in a per-participant random order, so the target emotion is never revealed.
- After the induction and the baseline: SAM and the six emotion items. After each **sub-block**: the six emotion items and a **short NASA-TLX** of three items (mental demand, effort, frustration; raw, 0–100; Hart & Staveland, 1988; Hart, 2006), so mood and workload are known for every menu in every emotion. After the three sub-blocks of an emotion block the participant also **ranks the three menus** by preference.

Expected pattern: the target item rises after its induction compared with baseline, and SAM moves in the expected direction (for example, arousal up for stress and frustration, valence down for sadness). Report these checks before using a block's data to train a model. The three sub-block ratings also show whether the emotion lasted through all three menus (it should not fade systematically with sub-block position; the Latin square balances any fade across menus).

## Ethics

- Participants are told up front, in general terms, that some activities are designed to influence how they feel. They are told the specifics only at the debrief.
- The debrief lists exactly which manipulations they experienced and asks again for permission to use their data. If they choose deletion, the data is removed automatically.
- Inductions are short and mild. The researcher checks the participant's wellbeing at the end, especially after stress, frustration or sadness.

## References

- Baker, R. S., D'Mello, S. K., Rodrigo, M. M. T., & Graesser, A. C. (2010). Better to be frustrated than bored. *International Journal of Human-Computer Studies, 68*(4), 223–241.
- Boucsein, W. (2012). *Electrodermal activity* (2nd ed.). Springer.
- Bradley, M. M., & Lang, P. J. (1994). Measuring emotion: The Self-Assessment Manikin and the semantic differential. *Journal of Behavior Therapy and Experimental Psychiatry, 25*(1), 49–59.
- Ceaparu, I., Lazar, J., Bessiere, K., Robinson, J., & Shneiderman, B. (2004). Determining causes and severity of end-user frustration. *International Journal of Human-Computer Interaction, 17*(3), 333–356.
- Dedovic, K., Renwick, R., Mahani, N. K., Engert, V., Lupien, S. J., & Pruessner, J. C. (2005). The Montreal Imaging Stress Task. *Journal of Psychiatry & Neuroscience, 30*(5), 319–325.
- Eastwood, J. D., Frischen, A., Fenske, M. J., & Smilek, D. (2012). The unengaged mind: Defining boredom in terms of attention. *Perspectives on Psychological Science, 7*(5), 482–495.
- Gross, J. J., & Levenson, R. W. (1995). Emotion elicitation using films. *Cognition and Emotion, 9*(1), 87–108.
- Hart, S. G. (2006). NASA-Task Load Index (NASA-TLX); 20 years later. *Proceedings of the HFES Annual Meeting, 50*(9), 904–908.
- Hart, S. G., & Staveland, L. E. (1988). Development of NASA-TLX. *Advances in Psychology, 52*, 139–183.
- Isen, A. M., & Levin, P. F. (1972). Effect of feeling good on helping: Cookies and kindness. *Journal of Personality and Social Psychology, 21*(3), 384–388.
- Jennings, J. R., Kamarck, T., Stewart, C., Eddy, M., & Johnson, P. (1992). Alternate cardiovascular baseline assessment techniques: Vanilla or resting baseline. *Psychophysiology, 29*(6), 742–750.
- Kirschbaum, C., Pirke, K. M., & Hellhammer, D. H. (1993). The 'Trier Social Stress Test'. *Neuropsychobiology, 28*(1–2), 76–81.
- Lehrer, P. M., & Gevirtz, R. (2014). Heart rate variability biofeedback: How and why does it work? *Frontiers in Psychology, 5*, 756.
- Lench, H. C., Flores, S. A., & Bench, S. W. (2011). Discrete emotions predict changes in cognition, judgment, experience, behavior, and physiology. *Psychological Bulletin, 137*(5), 834–855.
- Markey, A., Chin, A., Vanepps, E. M., & Loewenstein, G. (2014). Identifying a reliable boredom induction. *Perceptual and Motor Skills, 119*(1), 237–253.
- Schaefer, A., Nils, F., Sanchez, X., & Philippot, P. (2010). Assessing the effectiveness of a large database of emotion-eliciting films. *Cognition and Emotion, 24*(7), 1153–1172.
- Scheirer, J., Fernandez, R., Klein, J., & Picard, R. W. (2002). Frustrating the user on purpose. *Interacting with Computers, 14*(2), 93–118.
- Ulrich, R. S., Simons, R. F., Losito, B. D., Fiorito, E., Miles, M. A., & Zelson, M. (1991). Stress recovery during exposure to natural and urban environments. *Journal of Environmental Psychology, 11*(3), 201–230.
- van Tilburg, W. A. P., & Igou, E. R. (2012). On boredom: Lack of challenge and meaning as distinct boredom experiences. *Motivation and Emotion, 36*(2), 181–194.
- Westermann, R., Spies, K., Stahl, G., & Hesse, F. W. (1996). Relative effectiveness and validity of mood induction procedures: A meta-analysis. *European Journal of Social Psychology, 26*(4), 557–580.

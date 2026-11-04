# Next to do

1. **Debug signal chime** – not playing on new signals.
   - Suspects: browser blocks sound until the page is clicked after each load (incl. after CONNECT); unlock listener stops after first try; chime polling stops when Auto Refresh is off.
   - Draft fix (not tested on Mac): `/mnt/project-files/backlog-drafts/chime-fix-draft.patch`.
2. **Analyse 15m ADX turn + 5m breakout trades** – 15m ADX slope turns negative → positive and breaks out while 5m ADX also breaks out. pradeep thinks these are big winners (~100% win).
   - Agree rules first (draft questions in thread "Analyse 15m ADX turn plus 5m breakout trades"), then test on 2025 and 2026.

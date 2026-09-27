with open('final_model_table3.md', 'r') as f:
    lines = f.readlines()

with open('final_model_table3_corrected.md', 'w') as f:
    for line in lines:
        if "| Model |" in line:
            f.write("| Model | Discovered Slugs | Aborted (DB Lookup) | Failed Parse | Logged DB Observations | Resolved | Unresolved | Editions | New Fields | Rejected |\n")
        elif "|---" in line:
            f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        else:
            f.write(line)

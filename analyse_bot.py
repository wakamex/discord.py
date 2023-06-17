# %%
import pandas as pd
from matplotlib import pyplot as plt
import numpy as np

from darkmode import darkmode_orange

DEFAULT_PFPS = [
    "https://cdn.discordapp.com/embed/avatars/4.png",
    "https://cdn.discordapp.com/embed/avatars/2.png",
    "https://cdn.discordapp.com/embed/avatars/3.png",
    "https://cdn.discordapp.com/embed/avatars/1.png",
    "https://cdn.discordapp.com/embed/avatars/0.png",
]

# %%
df = pd.read_csv("guild_members.csv")

# count cumulative joins without a 5 minute break
# date format "2021-05-11 07:27:17+00:00"
df["joined_at"] = pd.to_datetime(df["joined_at"], format="mixed")
df = df.sort_values(by="joined_at", ascending=True).reset_index(drop=True)
df["previous_joined_at"] = df["joined_at"].shift(1)
df["join_delta"] = df["joined_at"] - df["previous_joined_at"]
df["join_delta"] = df["join_delta"].dt.seconds / 60  # in minutes

# boolean column which will be True when `join_delta` > 5 and False otherwise
df["reset_point"] = df["join_delta"] > 5

# `cumsum` on a boolean column will create distinct groups each time `reset_point` is True
df["group"] = df["reset_point"].cumsum()

# groupby 'group' and create a running count within each group
df["consecutive_joins"] = df.groupby("group").cumcount()

# If you don't want to keep the 'group' and 'reset_point' columns, you can drop them
df = df.drop(columns=["reset_point", "group"])

# %%
df.loc[len(df) - 5 : len(df), ["joined_at", "join_delta", "consecutive_joins"]]

# %%
df.plot(x="joined_at", y="consecutive_joins");

# %%
df["is_raid"] = df['consecutive_joins'] > 5
df["raid_id"] = 0
for idx in df.index[1:]:
    if df.loc[idx, 'is_raid']:
        if not df.loc[idx-1, 'is_raid']:
            df.loc[idx, "raid_id"] = df.raid_id.max() + 1
        else:
            df.loc[idx, "raid_id"] = df.loc[idx-1, "raid_id"]

# %%
df.tail(50)

# %%
raid_id = 138
idx = (df.raid_id == raid_id) & (df.display_avatar.isin(DEFAULT_PFPS))
# print all display names
print(','.join([f'{x}' for x in df.loc[idx, "display_name"].values]))

df.loc[idx, "display_avatar"].value_counts()

df.loc[idx,"id"].to_csv("ids_to_ban.csv", index=False)

# %%
ids_to_ban = pd.read_csv("ids_to_ban.csv")
ids_to_ban = ids_to_ban["id"].values.tolist()
print(ids_to_ban)
print(type(ids_to_ban))
print(len(ids_to_ban))
# %%

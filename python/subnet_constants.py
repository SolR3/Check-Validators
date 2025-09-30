#############################
# Subnet threshold constants
#############################
MIN_STAKE_THRESHOLD = 4000 # TODO - Need some way to verify this
                           # This is the value used by the taoyield site
MIN_VTRUST_THRESHOLD = 0.01
MAX_U_THRESHOLD = 100800 # 2 weeks


####################################
# Printer color threshold constants
####################################
VTRUST_ERROR_THRESHOLD = 0.2
VTRUST_WARNING_THRESHOLD = 0.1
UPDATED_ERROR_THRESHOLD = 1080  # 3x normal subnet tempo (360 blocks)
UPDATED_WARNING_THRESHOLD = 720  # 2x normal subnet tempo (360 blocks)


#######################
# Hotkeys and Coldkeys
#######################
COLDKEYS = {
    "Rizzo": "5FuzgvtfbZWdKSRxyYVPAPYNaNnf9cMnpT7phL3s2T3Kkrzo",
    "Rt21": "5GZSAgaVGQqegjhEkxpJjpSVLVmNnE2vx2PFLzr7kBBMKpGQ",
    "OTF": "5HBtpwxuGNL1gwzwomwR7sjwUt8WXYSuWcLYN6f9KpTZkP4k",
    "Yuma": "5E9fVY1jexCNVMjd2rdBsAxeamFGEMfzHcyTn2fHgdHeYc5p",
}

# This is a fix to handle the subnets on which our coldkeys is
# registered on multiple uids.
MULTI_UID_HOTKEYS = (20,)

RIZZO_CHK_HOTKEY = "5FtBncJvGhxjBs4aFn2pid6aur9tBUuo9QR7sHe5DkoRizzo"

# These are only used as a fallback when we're not registered on
# the subnet and the hotkey can't be obtained via our coldkey.
RIZZO_HOTKEYS = {
    1: "5D1saVvssckE1XoPwPzdHrqYZtvBJ3vESsrPNxZ4zAxbKGs1",
    2: "5GWo5GoUpEXeX4VMg32eudaryBbNRWZo39uwiSqCEzZSX9s2",
    3: "5He5TL2hHRjU2R6MsPEwMUw4DTZnL9vszPwtCHag3vuDEjs3",
    4: "5F4pBNBg9JYUGk73ahd4vojhEJsoJNgDKNkGD2p7GHcZ6us4",
    5: "5CrJSaSUfYjuXdvoSgDzvvnxLScF3Rn8XFQaJ63WjKuymCs5",
    6: "5FEZFDwD9LrY55FSBQKEEUDo7biWa3MPRXHeaChHuuKG6is6",
    7: "5EUqYQaU8JHYVFx8Tckj3wr7KqujJMNBQTD8Li6ahYnfUjs7",
    8: "5DkVUF5APWRLLwLYJtZ48g71E4KyksaS2h6YC8LzrRSUR4s8",
    9: "5DRw8PR445TJucdq41t8JWfJBAobMKbS48NpDJogZ5CcZJs9",
    10: "5CDnwKeAereYBBpp6Cm723RMNiEjAPjaPLouQSKC625mCs1o",
    11: "5GZGoeDmDjTXj5bygq5o1J9uhiUPu21v3pj9U5FDrduSfs11",
    12: "5HKxhdGD5L4eoCywrW33aXYqsGM6WKzKvGjpk3jeE1MiAs12",
    13: "5H1ZCd4QnUdZCyMtKKAF4h6symfhMP3ACWawZJcNRC6hKs13",
    14: "5GRhNwkjgGwLmQdJpo2UBDephy4f1qDQzGJnKYWvHcSYBs14",
    15: "5FRa6jo542HuMNpZc9u5fE1uwJVNd5pMbKeoakzbkaCkLs15",
    16: "5GVwX9o86zh6BB2doUxWtV7iTcRc8weW1nPgo6aYkoSq5s16",
    17: "5CAXtLZwVj4aav8uk1GsPvdDmF9E5gV9rTEvfdSzNCsmZs17",
    18: "5G1G2kJPomq9xJttsfvX3XchywHvS1o2qUFCoUkPo5ShZs18",
    19: "5DCQd5vksHiBbShG5h8Y7NX3VebyHRGQGedX1Tmn8oFhDs19",
    20: "5ExaAP3ENz3bCJufTzWzs6J6dCWuhjjURT8AdZkQ5qA4As2o",
    21: "5HpZnAoVszxJjiyjkLqNmZXwDXHgF9NpbM9VAVJXD97pms21",
    22: "5FBk8NbxWLRboCqEL2oj1KXwSmmaC1nFmBBL4AzLEN5Qjs22",
    23: "5FsvvvUFcLvkpbuTZVURre6r1z16qwFtjh4YrznDVNP5ps23",
    24: "5CFVuUA496F4S417ZW9Yk6pZiKseAMTyG7fhG9zDU684vs24",
    25: "5E9vRSxypx39uaz747ZbwA2ey6gFGqFbxU6FuoaVd37KQs25",
    26: "5DWyg7EkJ76uUM71Uv5G4h9rrfqJdkyrsAm3J26Dntaucs26",
    27: "5FsNmzUoNRYLF4MvNyTAJA549ZksuuBtbXo5xuHp7iXoVs27",
    28: "5F1UJWEFGkUcyJvfAN2T3SePGP5PgXu6fmmVfUdfKhUe6s28",
    29: "5G72cxTnxfyjD7EdhEthfe51GXY7hH3uaFHB8BhQ28oUEs29",
    30: "5FXHo9q4XBaD9zmdJ1b1wfECANw1LosjawfqZ1ugKJ2jYs3o",
    31: "5CkJ2LxMMuidAGUFn8X7Np1f8JShEzM9meTkviADmS14Ms31",
    32: "5HT7Mh62VZWTQ8BEm48CW9FZUzg44aBqcJm5R268dmwPms32",
    33: "5FZe9Mpo5dLXfhGZ4VjRnw6dmz9LVPp6nzqPyDfaS9BLKs33",
    34: "5EUQ8xz58REZ25sPPCMEgxVcnLynXyD7RWzNUeUcDSGYMs34",
    35: "5CoDR6FSgD1gj75F6cXeiQBVayXrzpcwKAbWfjQPRhnNts35",
    36: "5C5xWaJRpgdmdq1m6MHvgoABCGS2SC9h6Bvb9T6bQcVhhs36",
    37: "5Gs7Haud4RHNhvm2AN1q1StxvVch1jZNm8Ab6P5aCyXQNs37",
    38: "5FWvzgKYhu1nEXJERw6HHVZB1DKY9uMzerke4WHSSkVJPs38",
    39: "5Ey1UfVxVcL6caSr6zmhaKGrzZWsDmLjAH8ksjnKRuPZns39",
    40: "5GBUVT6eJHSU8vNBp6L6WGAmed4yf9hF5pqn9Y3iZ5njns4o",
    41: "5CmJzrj2vVGnpYHWoKRMRkntsgRJjzfFmbgZMXu4Rg2wEs41",
    42: "5DAP6nAavo4HgvkoUaZDVDBzfGzjc8AgG9o2Zga4irQqzs42",
    43: "5FhfG938jggJhQX88zELojWpUEoKu2PgBnoFXnh3cs1CYs43",
    44: "5EP6ARde6uYsWA6aTdeNkCesS7zwNmrnTSE1xMNMHyribs44",
    45: "5DnNzmms8Pg7YekmHsDjJXKUMYeBG8ziM9nMj19pfiH5vs45",
    46: "5Ff4i1yuQbLPqoRkxanYAZoRiJcNLaAnDoJWso5UZw92es46",
    47: "5E6tY1M7B4s8xtRg4QhUTVCC7V73jBy27x9gxmfBTRhims47",
    48: "5CPdzg3iv7w3tj9WkhSxRct5YrhTPd6sSY7mn5x5Y7YCXs48",
    49: "5EPdhbd4RzzRiPbEXssg6fQ3s8CU1M8kLG2L2WiXghCSas49",
    50: "5Ci3icAs5c9vMUFkjT1nDqfD8N8hXEFkgfe161aT7AYB1s5o",
    51: "5HmG5VN4MjnGX9nvr4muMAhGMHcADhhKeTreMTkTdkCr6s51",
    52: "5F9PB8E4sknh2rPcBsC5MLReP5hWg3cxnPvXj7By7yYJfs52",
    53: "5CArYVbJB9BiEVDvYrEeMKn9xgYq5VUCBmV4Ey3hVKRTgs53",
    54: "5GQqAhLKVHRLpdTqRg1yc3xu7y47DicJykSpggE2GuDbfs54",
    55: "5HC89ZBDkB6SEeeVN7bn8k5EvK6NPRL5MjVkFobsRjDNas55",
    56: "5GWksn9hpS3LWSSn6mzAqQwQtjyBQqXwK1Lq9ghK4Z84Ds56",
    57: "5CnjBb99HrEwEAav3WW9TH99fLKvi51EpEcwpokJAA9JRs57",
    58: "5D8GfQFmkCc8V434p5RLwZrWVCTGJfqaYUT9oGzugvGc9s58",
    59: "5ChTYCkTrJ5bsR2mh3HtVZqpvmZvLuSF1UpuA1okgwBsws59",
    60: "5E4Grhiu6gNb1KJ38zpYr9dwwYpViDXMksNYxDeppv84js6o",
    61: "5ECKL59gbSMghFSYqsBJEQ2HGa3zCm56A2mRX46yGxBv7s61",
    62: "5GuRsre3hqm6WKWRCqVxXdM4UtGs457nDhPo9F5wvJ16Ys62",
    63: "5GzjAcUcD3pFk5ybJ1qP4tMfnyk2Kh3SX8R2kMQwPU2dTs63",
    64: "5HTn5NcpCMabvHysyESrNirifM4GQqQJSnBT64kM7qCBas64",
    65: "5HY9hGb2tY5zjjcbS1puJoQQXo1cYMrwWnpTeMYRbQjgxs65",
    66: "5GgEAyGk7RJHbm2twPnZEFooXZa1JSUPkv8ysnWaneVeLs66",
    67: "5HTPDpG81FaLZCxJFaVZzg9qUhzFzEYStYk54gWCDKmXrs67",
    68: "5EXXUEhZmqG9fzyURV6YfqEEAHK1gwrKpfVD57iHgq7Wss68",
    69: "5FWeytadh3yDjSLscb2H3pJzobVEjnmjEUkShuAvcQppgs69",
    70: "5HQNiYELL2w7AQdFC7LPV9zEbZpCuktLHxveCnwe3aok9s7o",
    71: "5GeEtY7Ars1FbSKhueoffzLHrYgw3rxn7eF6egicCbWmNs71",
    72: "5GKXPseh2DDXYC8uYs3M5MWaqfj1TDNrJdNMA4zgZ9oSis72",
    73: "5DsegbQWSYjkfthAReaN5GbPf7HqQX2EbTZoDhWATRFxYs73",
    74: "5CthoCAywg2TS5J8G62YmACkDHF1mgCyX1G1ch8EC6Dv6s74",
    75: "5F9u6pymyXKHZWn1BSmimT9ux5LST9DRXiRHT8NQwTYpFs75",
    76: "5GTcAfWD8bm76DgRjhtH1Gs2o2DHjkUUmhoFtPdp17NHDs76",
    77: "5FEqzC97AnCJVrYtLiSwmzhpHJhdnmAwTko9ebpWTmCsas77",
    78: "5DypFQuSzKkQqKFNsa5Xgg8qNxkV5UPDhtnXRaj7jHxDbs78",
    79: "5GKj3UR5WchME5QKgzWY3j383qaYz3WuvHrhxS1t9MzF8s79",
    80: "5EPQVhNs7xBjw3mhDsv5qyViJzn8YwpGLUQsLzCCFCn7Ns8o",
    81: "5GneYj1pgFiZz1CM2m9W7aiJb3cdskqBERq8bsTvFg948s81",
    82: "5CDgbBhSpePngE1Ef3LTvfu3opMD2wEXn4NqfUfJXDm5Ks82",
    83: "5CJmEokTjtqe4bsXsNfEzTv9bjW26R4A4iYS7hi1nz5p4s83",
    84: "5CUbSHpf2AAMvsyKztvaF8BgoMmPAUdLLB1oYNmn23Mcts84",
    85: "5EUqqYFhNeYbZCm6UTQ3SULNDibNs2ZVjukV8pqeYZA6ms85",
    86: "5F9FAMhhzZJBraryVEp1PTeaL5bgjRKcw1FSyuvRLmXBds86",
    87: "5GTy4rwwqLnpPTGRPJGhELWXpqnsnwacRuRLFXWMHj4Wks87",
    88: "5Enr7Tyn2G3hFNcpRYoLFaLTQssyKwkB2r3gufNKarzDZs88",
    89: "5GQi6E5iK1sB7BdRkZyqhFL2VvHeQCGwsQQUL3ZrZXk59s89",
    90: "5G93HXFjvF7PNoVse1y1TSCDL8y4sbocN9vx4Hn1dkSPss9o",
    91: "5D9huaJLhdkmRTjJ3qyHtSFhj7yYUNqsE92DEJHvnBBWBs91",
    92: "5CSLw6MTmuYkaJZMJ3jS2uCgNqXwxCJ3B1FsHAM7kjWtcs92",
    93: "5FUPAUQPGXUqWvAn71qWKMaZjjWGbsEVjVuQoCRekUwvHs93",
    94: "5F2SaUVxK3mb2WnzZiEaHLA3CssR9ATXfPfdkWzcfgaR9s94",
    95: "5HYDvnBMpMSh1VM8cJV7GmhQuPG9ShnLCsSc4h1UnaxL6s95",
    96: "5CwLbF27c41nygMoGYqyhYkbifm2MfJyknWJLCVJzvjaxs96",
    97: "5Gs5B4KZDmxax8T3vPaYM8bNQLWyCjjsUDBoBTKaXZ15Qs97",
    98: "5H3RU1zKtVVYjW75c6QHo7n3qnP9TfXSEGFDoGUChGjbns98",
    99: "5CrGhhemVi8e77LRpogbQEvuqvBssaEYz2EzrUfNR5bJ1s99",
    100: "5F3q47PxU4SjH49HWoUtRhfy8q4aShhx3yQHPHPpSo23s1oo",
    101: "5FnFUXkjerRPXqC2t8sEZNHFerobwmE8ZUAfzjCjVazzs1o1",
    102: "5DAjvdMgvyBGQ1WHWchdu2gJv8yYVwUy8guY67Ytcp6Rs1o2",
    103: "5FJ4NPCaw9Mzj1mBa8opyk9kaab7RCuSBqA64akkw9b8s1o3",
    104: "5EWmTBPfx1JqqKfkR5ZnhidFuF5HeAvuhSCbiQBskicQs1o4",
    105: "5FmsqfCNY2RR42VHG2UH3fkg25HxrJDRhwm97gftNj1hs1o5",
    106: "5Coy5vsw42ZNHZieVPn5pCNdG7A3nq8R4LrMwnffSgdzs1o6",
    107: "5CGKJv9qfyWkYKAJsG4zW6SrxLkBeRgRL9v5AYy4uQ6is1o7",
    108: "5H99nv2hD8MkyiuPLXkLgGvghF3ZyrBULt7HVJZ8WLQjs1o8",
    109: "5Fh7wcBuW2d2qzZTwJ6gbQkxV37wHQpfApo7BMriEFxns1o9",
    110: "5GNsmgiydC6sC9HLhs435cegTm73YfDWXNFsSxcUJiSps11o",
    111: "5Gx1onS4YbtK1qDRSqhdVtjjwd5jKm81NPUD9FbCLPYVs111",
    112: "5FdtBrmYC1WHKfqs34ZDpQeQqZgQjY5D32EcYChswhiWs112",
    113: "5F7b8yV8SMMoB8RajYhSBUir6jL1Nsb4YbtDSVJy2RxJs113",
    114: "5Hmch6d6hc3ASpWvPMQuuKJc4h6wviu8LDMZ7SvjbaDhs114",
    115: "5HpdErNxQCaAuhESgs3fC4TQ9YehxbfNCYK3CS2YBSjfs115",
    116: "5DJYCz1kSbNEdSF3SfPPZkUDvGNQykW2K6d7XsSPKXATs116",
    117: "5C88hCYVDVkp8UCaf3G8WT6Qoi9Qj8dEeBGx1kH6R51ys117",
    118: "5CFtzzb4vym9eysfeF9cxxp6D7gksuUVTKYNq1mchnrMs118",
    119: "5FHLhcVcP2vNxpBPUfeb3MmUqowPMKj2NLs2CcLpZfuns119",
    120: "5DUP7VmjwWB2LuhHXfb5emLxKuKVhXCze5uVuBQD4aXHs12o",
    121: "5GWHesgxgrbeUTtQhpVhcVexFK2gbRJwAkU2JX2LdWRSs121",
    122: "5CZoa8Uw2GjkHfg3vybiiG5iGGAqqbDR6BdvhqJbj2Avs122",
    123: "5GzaskJbqJvGGXtu2124i9YLgHfMDDr7Pduq6xfYYgkJs123",
    124: "5FKk6ucEKuKzLspVYSv9fVHonumxMJ33MdHqbVjZi2NUs124",
    125: "5HCHD7JoKGbYLUZBN9JCokGjTTGTn9SZiQ7pCYrpcMyFs125",
    126: "5HmkWGB5PVzKCNLB4QxWWHFVEHPAbKKxGyoXW7Evs38gs126",
    127: "5G8pZG5zKEuhykkCYifxYhhXtyWWg6XuGHHkJxmZjgHhs127",
    128: "5EAb8sesrpfVi9ftcsgKkM7RfHbYotdz53hGCEZmkrpLs128",
}

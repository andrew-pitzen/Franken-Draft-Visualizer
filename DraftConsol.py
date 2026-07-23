import re

def DraftConsol(text):
    """
       List of draftable objects

       Ability
       Tech
       Breakthrough
       Agent
       Commander
       Hero
       Mech
       Flagship
       Commodities
       PN
       Homesystem
       Startingtech
       Startingfleet
       Bluetile
       Redtile
       Draftorder
       """
    round = 0
    round2 = 0
    linesinhand = False
    category_check = re.compile(r"([A-Z]+) \((\d+)/\d+\):")
    total_cards_counter = re.compile(r"Total Cards: (\d+)")
    master_list = []
    round_list = {}
    category_dic = {}
    category_counter = {}
    current_cat = None
    current_count = None
    cat_value = ""

    allroundstextlist = []
    round_text = ""
    current_total_cards = 0
    old_total_cards = 0

    for line in text.splitlines(True):
        if line.strip() == "Your current Hand of drafted cards:":
            round += 1
            linesinhand = True
        y = total_cards_counter.match(line.strip())
        if y is not None:
            linesinhand = False
            current_total_cards = y.group(1)
            if old_total_cards == current_total_cards:
                allroundstextlist.pop()
            old_total_cards = current_total_cards
            allroundstextlist.append(round_text)
            round_text = ""

        if linesinhand is False:
            continue
        round_text += line

    for round_text in allroundstextlist:
        current_cat = None
        round_list = {}
        master_list.append(round_list)
        for line in round_text.split("\n"):
            if not line:
                continue
            m = category_check.match(line.strip())
            if m is not None:
                #add current_cat and cat_value to round list
                if current_cat is not None:
                    cat_value_dif = calc_dif(cat_value, category_dic.get(current_cat)).strip()
                    round_list[current_cat] = cat_value_dif
                    category_dic[current_cat] = cat_value
                current_cat = m.group(1)
                current_count = m.group(2)
                if category_counter.get(current_cat, "0") != current_count:
                    category_counter[current_cat] = current_count
                else:
                    current_cat = None
                cat_value = ""
            elif current_cat is not None:
                cat_value += line + "\n"
        if current_cat is not None:
            cat_value_dif = calc_dif(cat_value, category_dic.get(current_cat)).strip()
            round_list[current_cat] = cat_value_dif
            category_dic[current_cat] = cat_value
        #print("************")
        #print(f"Round {len(master_list)}")
        #print("************")
        #for key,value in round_list.items():
            #print(f"{key}:")
            #print(value)
            #print("")
    #print("Master List")
    return(master_list)

def calc_dif(new_value, old_value):
    if not old_value:
        return new_value
    #print(new_value)
    return new_value[len(old_value):].strip()




if __name__ == '__main__':
    DraftConsol(text)

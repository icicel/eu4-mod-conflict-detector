import os, re, zipfile

# config here!

# directories
# workshop mods are stored as folders and local mods as zip files, so i have to differentiate
# a typical directory would be:
# workshop dir = "C:/Program Files (x86)/Steam/steamapps/workshop/content/236850/"
# local_dir = "C:/Users/Admin/Documents/Paradox Interactive/Europa Universalis IV/mod/"
workshop_dir = "C:/Program Files (x86)/Steam/steamapps/workshop/content/236850/"
local_dir = "C:/Users/HammarlundIsak/Documents/Paradox Interactive/Europa Universalis IV/mod/"

# (mostly to ignore "complete overhaul"-type mods that you already know will conflict with everything)
blacklist = []

# you know what a whitelist is! it will be prioritized over the blacklist
whitelist = []

# only compare mods that are currently enabled, requires a special file where the enabled status is stored
# a typical location would be:
# dlc_load_location = "C:/Users/Admin/Documents/Paradox Interactive/Europa Universalis IV/dlc_load.json"
only_enabled_mods = False
dlc_load_location = "C:/Users/HammarlundIsak/Documents/Paradox Interactive/Europa Universalis IV/dlc_load.json"




# ok here we go
# warning: there's a lot of list comprehensions.
# as much as i love list comprehensions i will admit that they are hard to read

# returns a file in a mod
def get_mod_file(mod_path, file_path, is_archive):
    if is_archive:
        return str(zipfile.ZipFile(mod_path, "r").read(file_path), "utf-8")
    else:
        return open(mod_path + "/" + file_path, "r").read()

# the descriptor file carries metadata about the mod, such as its written name and what directories it replaces
# it is always stored in the mod's main directory
def get_from_descriptor(key, mod_path, is_archive):
    return [re.search(key + "=\"(.+)\"", l).group(1) # i also love regex
            for l in get_mod_file(mod_path, "descriptor.mod", is_archive).split("\n")
            if l[:len(key) + 1] == key + "="]
def get_from_external_descriptor(key, file):
    # descriptor files are also stored directly in the local_dir, in addition to being in the respective mod directory
    # these "external" descriptor files signal to the game launcher what mods are installed
    # the launcher also refers to them when telling us what mods are enabled
    return [re.search(key + "=\"(.+)\"", l).group(1)
            for l in open(local_dir + file, "r").read().split("\n")
            if l[:len(key) + 1] == key + "="]

# returns all files in a directory or archive respectively, including files in subdirectories
def get_all_files(path, subpath=""):
    filelist = []
    for f in os.listdir(path + "/" + subpath):
        if f.count(".") != 0: # if file is not directory
            filelist.append(subpath + f)
        else:
            try:
                for subfile in get_all_files(path, subpath + f + "/"): # i also love recursive functions
                    filelist.append(subfile)
            except NotADirectoryError: # file with no file extension (folder impostor)
                filelist.append(subpath + f)
    return filelist
def get_all_archive_files(archive_path):
    # a bit simpler due to the way zipfile.ZipFile() reads zip files
    return [f.filename for f in zipfile.ZipFile(archive_path, "r").infolist()
            if not f.filename[-1] == "/"]

# returns a list of all defines in all defines files of the mod
# yeah, defines files need that special treatment
# they are always .lua files located at /common/defines/
def get_defines(mod, is_archive):
    defines = []
    if is_archive:
        for f in get_all_archive_files(local_dir + mod):
            if "common/defines/" in f and f[-4:] == ".lua":
                defines += get_mod_file(local_dir + mod, f, True).split("\n")
    else:
        # no need to get_all_files() here unlike above, we just need the defines folder after all
        for f in os.listdir(workshop_dir + mod + "/common/defines"):
            if f[-4:] == ".lua":
                defines += get_mod_file(workshop_dir + mod, "/common/defines/" + f, False).split("\n")
    return [re.search("[\t ]?(.+?)[\t =]", line).group(1)
            for line in defines
            if "NDefines" in line.split("-", 1)[0]] # <- avoids commented lines

# sends all files in changes_list to changes (a dictionary)
# the data structure this function uses:
# changes = {
#     "path/directory/textfile.txt": ["mod1", "mod2"],
#     "path/directory/image.bmp": ["mod2", "mod3"],
#     "path/defines/NDefines.VALUE": ["mod1", "mod3"]
# }
# in the example, it means that both mod1 and mod2 make changes to path/directory/textfile.txt, which is a conflict
def collect_changes(changes_list, mod, is_archive, lower=True):
    global changes
    for f in changes_list:
        ff = f.lower().split("/") if lower else f.split("/")
        if "defines" in ff and ff[-1][-4:] == ".lua": # here's where defines files get handled differently
            collect_changes(["/".join(ff[:-1]) + "/" + d
                             for d in get_defines(mod, is_archive)],
                            mod, is_archive, False)
        elif len(ff) != 1:
            path = "/".join(ff)
            try:
                if mod not in changes[path]:
                    changes[path].append(mod)
            except KeyError:
                changes[path] = [mod]



# no more lame functions! only the real deal from here on out!

# find all enabled mods and put them in the whitelist
# contains a bit of yucky .json parsing but i don't care, it works (i think)
if only_enabled_mods:
    dlc_load = open(dlc_load_location, "r").read()
    for line in dlc_load.split("\"disabled_dlcs\"")[0].split("\",\""):
        descriptor = re.search("mod/(.+?\.mod)", line).group(1)
        mod_path = get_from_external_descriptor("archive", descriptor)
        if not mod_path:
            mod_path = get_from_external_descriptor("path", descriptor)
        whitelist.append(mod_path[0].split("/")[-1])

# grab all mod locations
workshop_mods = [f for f in os.listdir(workshop_dir) if f.count(".") == 0
                 and (f in whitelist if whitelist else f not in blacklist)]
local_mods = [f for f in os.listdir(local_dir) if f[-4:] == ".zip"
              and (f in whitelist if whitelist else f not in blacklist)]

# get mod names and check availability of mods at the same time
mod_names = {}
brokens = []
for m in workshop_mods:
    try:
        mod_names[m] = get_from_descriptor("name", workshop_dir + m, False)[0]
    except FileNotFoundError:
        # happens if
        # 1. the mod folder is empty (solution: delete the folder. what? there's clearly not a mod there)
        # 2. there's a binary archive (solution: unpack the archive with 7zip or similar)
        # 3. the descriptor file is not named descriptor.mod (solution: rename it to descriptor.mod)
        # i guess this program could do these things automatically but naahhhh
        brokens.append(m)
if brokens:
    print("Could not parse these workshop mods:")
    quit(print(brokens)) # the user will have to fix these manually
    # one day i will learn proper error handling using raise and such. however, this is not that day
for m in local_mods:
    mod_names[m] = get_from_descriptor("name", local_dir + m, True)[0]
# get this for formatting at the end
longest_name_length = len(mod_names[max(mod_names, key=lambda x:len(mod_names[x]))])

# build the changes dictionary
# changes = {
#     "path/directory/textfile.txt": ["mod1", "mod2"],
#     "path/directory/image.bmp": ["mod2", "mod3"],
#     "path/defines/NDefines.VALUE": ["mod1", "mod3"]
# }
changes = {}
for m in workshop_mods:
    print("Scanning: " + mod_names[m])
    collect_changes(get_all_files(workshop_dir + m), m, False)
for m in local_mods:
    print("Scanning: " + mod_names[m])
    collect_changes(get_all_archive_files(local_dir + m), m, True)
# remove files with no conflicts (only one mod makes changes to them)
for c in [c for c in changes if len(changes[c]) == 1]:
    del changes[c]

# change the data structure to nested dictionaries:
# conflicts = {
#     "path/directory": {"mod1": ["textfile.txt"], "mod2": ["textfile.txt", "image.bmp"], "mod3": ["image.bmp"]},
#     "path/defines": {"mod1": ["NDefines.VALUE"], "mod3": ["NDefines.VALUE"]}
# }
# this is necessary for representation of one specific problem - mods that replace an entire directory
conflicts = {}
for filepath, mods in changes.items():
    path = "/".join(filepath.split("/")[:-1])
    file = filepath.split("/")[-1]
    if not path in conflicts:
        conflicts[path] = {}
    for mod in mods:
        if mod in conflicts[path]:
            conflicts[path][mod].append(file)
        else:
            conflicts[path][mod] = [file]

# so, yeah! some mods replace entire directories. in the data structure, this is represented as:
# "path/directory": {"mod4": ["EVERYTHING"]}
# should be clear enough for the end user!
for m in workshop_mods:
    for r in get_from_descriptor("replace_path", workshop_dir + m, False):
        if not r in conflicts:
            conflicts[r] = {}
        conflicts[r][m] = ["EVERYTHING"]
for m in local_mods:
    for r in get_from_descriptor("replace_path", local_dir + m, True):
        if not r in conflicts:
            conflicts[r] = {}
        conflicts[r][m] = ["EVERYTHING"]
for r in [r for r in conflicts if len(conflicts[r]) == 1]:
    del conflicts[r]

if not conflicts:
    print("\nNo conflicts detected?! Impossible, perhaps the archives are incomplete.")
else:
    print("\nBeep beep, CONFLICTS DETECTED! Printing to file. I love my job!")
    # omega-long string as output, classic
    # wowzers!!! list comprehension zoinkers!!!!! bazoinkskies!!!!
    # that moment when you format the entire output file in one line (well it's 6 lines but you get me)
    output = "\n\n".join([
                 p + "\n" + "\n".join([
                     mod_names[m] + "".join(" " for n in range(longest_name_length - len(mod_names[m])))
                     + " - " + ", ".join(conflicts[p][m])
                     for m in conflicts[p]])
                 for p in conflicts])
    open("conflicts.txt", "w").write(output)
    # due to the output's potentially extreme length, it is best viewed with word wrap OFF in notepad++

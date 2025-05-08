from sys import argv


def get_args(**arg_flags) -> dict:
    """
    get_args(flag_name = parameter_count ...)
    get_args()

    Kullanmak istediğiniz argüman bayraklarını argv'dan alır
    Bayrak adına, bayraktan sonra verilecek parametre sayısını eşitler
    Belirtilmeyen argümanlar yok sayılır
    Eğer bir argümanın yeterli sayıda parametresi verilmemişse, İstisna (Exception) fırlatır

    Eğer hiç argüman verilmemişse, argv'daki tüm bayraklar ve parametreleri alınır

    Anahtarları bayrak adları olan ve değerleri;
        parameter_count > 0 ise parametre listesi
        aksi halde None (bayrağın verilip verilmediğini "flag_name in arg_dict" ile kontrol edebilirsiniz)

    Örnek:
        Programınız şu şekilde başlatılmış olduğunu varsayın:
        python program.py -a -user username password -count 12

        Fonksiyonu şu şekilde çağırmalısınız:
            get_args(a=0, user=2, count=1)
            veya
            get_args()
        Bu şu şekilde döner:
            {"a": None, "user": ["username", "password"], "count": ["12"]}

    """
    arg_dict = dict()
    arg_index = 0
    if arg_flags:
        arg_index += 1
        while arg_index < len(argv):
            flag = argv[arg_index]
            flag = flag[1:]  # bayraktaki '-' işaretini kaldır
            if flag in arg_flags:
                if arg_flags[flag] == 0:
                    arg_dict[flag] = None
                else:
                    params = list()
                    for _ in range(arg_flags[flag]):
                        arg_index += 1

                        if arg_index >= len(argv) or argv[arg_index].startswith("-"):
                            raise Exception(
                                f"Bayrak '-{flag}' için yeterli parametre verilmedi"
                            )

                        params.append(argv[arg_index])
                    arg_dict[flag] = tuple(params)

            arg_index += 1
    else:
        flag = None
        params = list()
        while arg_index < len(argv):
            if argv[arg_index].startswith("-"):
                if len(params) > 0:
                    arg_dict[flag] = tuple(params)
                else:
                    arg_dict[flag] = None
                flag = argv[arg_index][1:]
                params = list()
            else:
                params.append(argv[arg_index])
            arg_index += 1

        if len(params) > 0:
            arg_dict[flag] = tuple(params)
        else:
            arg_dict[flag] = None
    return arg_dict
import PySimpleGUI as sg
a = ()
def start():
    layout1 = [[sg.Button("Next")]]
    window1 = sg.Window("Test",layout1,size=(300,300),finalize=True)
    event,values = window1.read()
    a = window1.CurrentLocation()
    print(a)
    print(type(a))
    while True:
        if event == sg.WIN_CLOSED:
            break
        if event == "Next":
            window1.close()
            nextp()
            break
def nextp():
    global a
    layout2 = [[sg.T("")]]
    window2 = sg.Window("Test2",layout2,location=a,size=(300,300),finalize=True)
    event,values=window1.read()
start()
import Global
import re
import os
import calendar
import datetime
import Functions
import pandas as pd
from ujson import load, dump
from calendar import monthrange

async def EveryFifteenMinutes(context):
    DownloadDatabase() 
    ObtainMergedCells()

async def EveryDaily(context):
    RemoveOutdated()

async def EveryMonth(context):
    dateDT = Functions.CurrentDatetime() + datetime.timedelta(days=1)
    
    GetGlobalVariables(dateDT)
    GetmeDFMonthRef()

# downloads ME and ADW sheets for previous, current and next month
# saves sheets as csv file
def DownloadDatabase():
    for folder in os.scandir('data/database'):
        for file in os.scandir(folder):
            os.remove(file)

    currentMonth = int(Functions.CurrentDatetime().strftime('%#m'))
    currentYear = int(Functions.CurrentDatetime().strftime('%y'))

    for deltaMonths in range(-1, 2):
        itMonth, itYear = Functions.timedelta_months(currentMonth, currentYear, deltaMonths)
        
        meDF = Functions.csv_to_dataframe(itMonth, itYear, 'me')
        meDF.to_csv(f'data/database/me/me_{itMonth}_{itYear}.csv', index=False)  

        adwDF = Functions.csv_to_dataframe(itMonth, itYear, 'adw')
        adwDF.to_csv(f'data/database/adw/adw_{itMonth}_{itYear}.csv', index=False)
    
    with open('data/status.json') as status_json:
        status_dict = load(status_json)

    status_dict['online sheets']['time'] = Functions.CurrentDatetime().strftime('%d/%m/%y at %#I:%M %p')

    with open('data/status.json', 'w') as status_json:
        dump(status_dict, status_json, indent=1)

def ObtainMergedCells():
    
    run_merged_cells = False
    
    with open('data/status.json') as status_json:
        status_dict = load(status_json)

    # obtain month last updated in database
    month_in_database = int(datetime.datetime.strptime(status_dict['merged cells']['time'], '%d/%m/%y at %I:%M %p').strftime('%#m'))
    
    # obtain current month
    month_now = int(Functions.CurrentDatetime().strftime('%#m'))
    year = int(Functions.CurrentDatetime().strftime('%Y'))

    # if current month and month in database is the same, but merged cells sheet has not stopped updating, run this
    # if current month and month in database is not the same, run this
    # this obtains the month of the online sheet 
    if (month_in_database == month_now and not status_dict['merged cells']['stopped']) or month_in_database != month_now:
        ME_df_with_merge = pd.read_html('https://docs.google.com/spreadsheets/d/1rXLXxWMSpb8hU_BRuI87jv7wS04tB6yD', index_col=0)[0].fillna('NIL')

        # obtains month of online sheet
        for x in range(5, 10):
            if re.search("[0-9]{1,2}-[A-Z]{3}", ME_df_with_merge.iloc[x, 5].upper()):
                month_in_sheet = datetime.datetime.strptime(ME_df_with_merge.iloc[x, 5].split('-')[1].upper(), '%b').month
                break
        
        # if month of online sheet is the same as current month, obtain merged cells
        if month_in_sheet == month_now:
            run_merged_cells = True

    if run_merged_cells:

        # reindex columns for sheet with merged cells
        ME_df_with_merge.columns = pd.RangeIndex(ME_df_with_merge.columns.size)

        # remove unnecessary rows and columns for sheet with merged cells
        # figures out number of days in month and then selects the appropriate number of columns
        ME_df_with_merge = ME_df_with_merge[ME_df_with_merge[ME_df_with_merge.columns[0]] != 'NIL']
        ME_df_with_merge = ME_df_with_merge.iloc[6:, [x for x in range(monthrange(year, month_in_sheet)[1] + 2) if x != 1]]

        # obtains the ME sheet with no merged cells
        ME_df_without_merge = Functions.OpenSheet(datetime.datetime(year, month_in_sheet, 1), 'me')

        # reindex columns for sheet with no merged cells
        ME_df_without_merge.columns = pd.RangeIndex(ME_df_without_merge.columns.size)

        # remove unnecessary rows and columns for sheet with no merged cells
        # figures out number of days in month and then selects the appropriate number of columns
        ME_df_without_merge = ME_df_without_merge[ME_df_without_merge[ME_df_without_merge.columns[0]] != 'NIL']
        ME_df_without_merge = ME_df_without_merge.iloc[5:, [x for x in range(monthrange(year, month_in_sheet)[1] + 1)]]

        # adds an extra column at the end of both dataframes
        # this is to allow for the program to iterrate through the whole row in the while loop below
        ME_df_with_merge['TEMP'] = 'NIL'
        ME_df_without_merge['TEMP'] = 'NIL'

        hit_merged_cell = False
        merged_cells_list = []

        # obtain all the merged cells
        for row in range(ME_df_with_merge.shape[0]):
            for column in range(ME_df_with_merge.shape[1]):

                cell_with_merge = ME_df_with_merge.iloc[row, column].upper().strip()
                cell_without_merge = ME_df_without_merge.iloc[row, column].upper().strip()

                # detects first instance of discrepancy (2nd cell of merged block)
                if cell_with_merge != cell_without_merge:
                    
                    # obtains the start of merged cell and status
                    if not hit_merged_cell:
                        name_in_ps = ME_df_with_merge.iloc[row, 0].upper().strip()
                        status_in_ps = re.sub('\s*/\s*', '/', ME_df_with_merge.iloc[row, column - 1].strip().upper())
                        merge_start_column = column - 1
                        hit_merged_cell = True         
                else:
                    
                    # detects one cell after the end of merged block and saves data
                    if hit_merged_cell:
                        merge_end_column = column - 1
                        merged_cells_list.append({'sheetName': name_in_ps, 'sheetStatus': status_in_ps, 'startDate': datetime.datetime(year, month_in_sheet, merge_start_column).strftime('%d%m%y'), 'endDate': datetime.datetime(year, month_in_sheet, merge_end_column).strftime('%d%m%y')})
                        hit_merged_cell = False

        # adds all the merged cells data to a json file
        with open('data/override/merged_cells.json', 'w') as merged_cells_json:
            dump(merged_cells_list, merged_cells_json, indent=1)

        status_dict['merged cells']['stopped'] = False
        status_dict['merged cells']['time'] = Functions.CurrentDatetime().strftime('%d/%m/%y at %#I:%M %p')

        with open('data/status.json', 'w') as status_json:
            dump(status_dict, status_json, indent=1)
    else:
        
        # kind of updates merged_cells.json but like badly
        
        # <<< stuff the below does >>>
        # if unmerged cells has a duty on a merged cells day, remove status from merged_cells.json
        # if unmerged cells has a different status from the merged cells (1st day), remove status from merged_cells.json
        with open('data/override/merged_cells.json') as merged_cells_json:
            merged_cells_list = load(merged_cells_json)
        
        for_checking = {}

        for index, x in enumerate(merged_cells_list):
            start_date = int(datetime.datetime.strptime(x['startDate'], '%d%m%y').strftime('%#d'))
            end_date = int(datetime.datetime.strptime(x['endDate'], '%d%m%y').strftime('%#d'))
            
            if x['sheetName'] not in for_checking:
                for_checking[x['sheetName']] = []
            
            for_checking[x['sheetName']].append({'INDEX': index, 'STATUS_IN_PS': x['sheetStatus'], 'DATES': [y for y in range(start_date, end_date + 1)]})
        
        ME_df = Functions.OpenSheet(datetime.datetime(year, month_in_database, 1), 'me')

        to_be_deleted = []
        
        for x in range(Global.TOP, Global.MIDDLE):
            name_in_ps = ME_df.iloc[x, 0].upper().strip()
            
            if name_in_ps in for_checking:
                for status in for_checking[name_in_ps]:
                
                    # if 1st day of merged cell status is different from ME_df, remove status from merged_cells.json
                    if re.sub('\s*/\s*', '/', ME_df.iloc[x, status['DATES'][0]].upper().strip()) != status['STATUS_IN_PS']:
                        to_be_deleted.append(status['INDEX'])
                        break
                    
                    # if duty or changeover present on any of the days in merged_cells.json, remove status from merged_cells.json
                    for date in status['DATES']:
                        status_in_ps = re.sub('\s*/\s*', '/', ME_df.iloc[x, date].upper().strip())
                        
                        if status_in_ps == 'X' or status_in_ps == '\\' or status_in_ps == 'SITE VCOMM':
                            to_be_deleted.append(status['INDEX'])
                            break

        # remover
        for index in sorted(to_be_deleted, reverse=True):
            del merged_cells_list[index]
        
        # indicating that the merged cells json has stopeed updating
        status_dict['merged cells']['stopped'] = True

        with open('data/status.json', 'w') as status_json:
            dump(status_dict, status_json, indent=1)
        
        with open('data/override/merged_cells.json', 'w') as merged_cells_json:
            dump(merged_cells_list, merged_cells_json, indent=1)

def RemoveOutdated():
    ref = {}

    fileName = [
        'parade_state_override',
        'rations'
    ]

    filePath = [
        'data/override/parade_state_override.json',
        'data/override/rations.json'
    ]

    for name, path in zip(fileName, filePath):
        with open(path) as file:
            ref[name] = load(file)
                    
    ref['parade_state_override'] = [x for x in ref['parade_state_override'] if Functions.DateConverter(x['endDate']) > Functions.CurrentDatetime().replace(tzinfo=None)]
    ref['rations'] = {k: v for k, v in ref['rations'].items() if k == 'everyday' or Functions.DateConverter(k) > Functions.CurrentDatetime().replace(tzinfo=None)}

    for name, path in zip(fileName, filePath):
        with open(path, 'w') as file:
            dump(ref[name], file, indent=1)

def GetGlobalVariables(dateDT=Functions.CurrentDatetime()):
    meDF = Functions.OpenSheet(dateDT, 'me')

    ref = {'sheetName': set(), 'commSec': set()}

    for flight in ['alpha', 'bravo', 'others']:
        with open(f'data/personnel/{flight}.json') as flightJson:
            flightList = load(flightJson)
        
        for x in flightList:
            ref['sheetName'].add(x['sheetName'])

            if x['commSec'] != 'NIL':
                ref['commSec'].add(x['commSec'])

    for row in range(meDF.shape[0]):
        target = meDF.iloc[row, 0].upper().strip()

        if target in ref['sheetName']:
            Global.TOP = row - 3
            break

    bottomHit = False

    for row in range(meDF.shape[0] - 1, 0, -1):
        target = meDF.iloc[row, 0].upper().strip()

        if target == 'NIL':
            continue

        if not bottomHit:
            if target in ref['commSec']:
                Global.BOTTOM = row + 1
                bottomHit = True
        else:
            if target in ref['commSec']:
                Global.MIDDLE = row
            else:
                break

def __MonthChecker(meDF, month, i, monthINT, meDFMonthRef):
    for x in range(15):
        if re.search('[0-9]{1,2}-[A-Z]{3}',  meDF.iloc[x, 5].upper()):
            if meDF.iloc[x, 5].split('-')[1].upper() == month[:3]:
                meDFMonthRef[monthINT] = month[:i]
                return True
    return False

def GetmeDFMonthRef():
    dateDT = Functions.CurrentDatetime()
    currentMonthINT = dateDT.month
    currentYearINT = dateDT.year

    with open('data/reference/MEdf_month_ref.json') as file:
        meDFMonthRef = load(file)

    monthFullList = [x.upper() for x in list(calendar.month_name[1:])]

    for x in range(-1, 2):
        monthINT, year = Functions.timedelta_months(currentMonthINT, currentYearINT, x)
        monthINT = monthINT - 1
        month = monthFullList[monthINT]

        for i in range(3, len(month) + 1):
            meDF = pd.read_csv(f'https://docs.google.com/spreadsheets/d/1rXLXxWMSpb8hU_BRuI87jv7wS04tB6yD/gviz/tq?tqx=out:csv&sheet={month[:i]}%20{year}').fillna('NIL')

            if __MonthChecker(meDF, month, i, monthINT, meDFMonthRef):
                break
    
    with open('data/reference/MEdf_month_ref.json', 'w') as file:
        meDFMonthRef = dump(meDFMonthRef, file, indent=1)
###Combination with hour correction###
####Library to collect Temperature, Humidity, pH, and Electrical Conductibity###
import time
# Import SPI library (for hardware SPI) and MCP3008 library.
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008
#import DHT Library
import Adafruit_DHT
#Import GPIO Library
import RPi.GPIO as GPIO
#TSL Light sensor
from python_tsl2591 import tsl2591

#importing Comma Separated value library
import csv
#import Request library used to send data to the server
import requests
#Used to save data into Json files
import json
#Used to get the date and time of the raspberry pi
from datetime import datetime


#setting the GPIO mode for the program
GPIO.setmode(GPIO.BCM)

#####pins on Raspberry Pi#####
#pin to control EC Sensor
ECpin = 16 
GPIO.setup(ECpin, GPIO.OUT)
#pins to control the Humidity and Temperature
dhtSensor0 = 20
dhtSensor1 = 21

#####Pins On ADC 0-7#####
#Analogue in from pin on MCP3008, 0-7
vinPin = 0
voutPin = 2
#pH sensor pin
pHpin = 6
#UV sensor pin
uvPin = 7

#####Relay Pins######
#Relay 1-4 corresponds to pins 26, 19, 13, 6
lightRelay = 6
misterRelay = 19
solutionRelay = 26

GPIO.setup(solutionRelay, GPIO.OUT)
GPIO.setup(lightRelay, GPIO.OUT)
GPIO.setup(misterRelay, GPIO.OUT)
GPIO.output(lightRelay, 1)
GPIO.output(misterRelay, 1)
GPIO.output(solutionRelay, 1)
##GPIO.setup(solutionRelay, GPIO.OUT)


###Variables to control light
lightCondition = 1 ###Light is original off

###Con

#setting the adafruit sensor to DHT22
sensor = Adafruit_DHT.DHT22

# Hardware SPI configuration:
SPI_PORT   = 0
SPI_DEVICE = 0
mcp = Adafruit_MCP3008.MCP3008(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE))

#####Light Sensor Constants#####
# Integration time
# The integration time can be set between 100 and 600ms,
# and the longer the integration time the more light the
# sensor is able to integrate, making it more sensitive in
# low light the longer the integration time.
INTEGRATIONTIME_100MS = 0x00
INTEGRATIONTIME_200MS = 0x01
INTEGRATIONTIME_300MS = 0x02
INTEGRATIONTIME_400MS = 0x03
INTEGRATIONTIME_500MS = 0x04
INTEGRATIONTIME_600MS = 0x05

# Gain
# The gain can be set to one of the following values
# (though the last value, MAX, has limited use in the
# real world given the extreme amount of gain applied):
# GAIN_LOW: Sets the gain to 1x (bright light)
# GAIN_MEDIUM: Sets the gain to 25x (general purpose)
# GAIN_HIGH: Sets the gain to 428x (low light)
# GAIN_MAX: Sets the gain to 9876x (extremely low light)
GAIN_LOW = 0x00
GAIN_MED = 0x10
GAIN_HIGH = 0x20
GAIN_MAX = 0x30

#light sensor configuration
lightSensor = tsl2591()
lightSensor.set_timing(INTEGRATIONTIME_100MS)
lightSensor.set_gain(GAIN_MED)
#####Name for the Files that are save as CSV######
name = ["EC", "Full", "Humidity", "Humidity_Outside", "IR", "Lux", "Temp", "Temp_Outside", "UV", "pH"]

#####Constants#####
#Firebase url that we will send the data to
firebase_url = 'https://seniordesign-e59ca.firebaseio.com/'
#resistance in ohms for the EC Sensor
rKnown = 965
#how many times the data is collected
timeCollected = 0
#How many time the light is on
timeOn = 0
#number of times the program ran
timeRun = 0
#number to time Mist
timeMist = 0
#calibrationslope
pHcal = 8.098
#pH: voltage per step
pHstep =.002346
#voltage steps of a 1024 level adc
voltageStep = float(3.3/1024)


#####Variables changed by the USER#####
#Time interval in minutes for collecting data
sensorInterval = .5 #5 mins intervals
#Time interval in minutes for running the lights
lightInterval = 1 #30 secs
#Mister interval
misterInterval = .5 #30 secs

#Cell Constant
K = float(.61)
#total seconds in a hour to control loop
totSec = (59*60) + 59
#finding the lux, Ir, visible light
def visibleIr():
    return lightSensor.get_full_luminosity()
def luxLight(full, ir):    
    return lightSensor.calculate_lux(full, ir)
    
#Finding the UV Light index that the plants are receiving
#still need to work on this!!!!
def uvIndex(pin):
    #Reading the analog input on the pin
    self = float(mcp.read_adc(pin))
    #calculating the voltage
    return (self * voltageStep)*10
    #categorizing the voltages into UV index
    ##return selfVoltage//1
    
#Sen - which sensor to get the data.
def tempAndHum(sen):
    return Adafruit_DHT.read_retry(sensor, sen)

#Find the pH without callibration
def pHLv(pin):
    pHin = float(mcp.read_adc(pin))
    print(pHin)
    pH = float((pHin*-pHstep*pHcal)+17.67)
    print(pH)
    return pH

#find the phConstant when submerged with EC Sensor
def pHConstant(pHini, pin):
    pHin = float(mcp.read_adc(pin))
    return float((pHini-15.67)/(pHin*-pHstep))

#Ec Calibration is the EC of the solution used for callibration
#If we are using with pH sensor in water, we must recalibrate the EC
#and there must be at least a one second delay from using the EC sensor
#and the pH sensor as to not have the voltage from EC affect pH that much
def cellConstant(ECCalibration, pin):
    GPIO.output(pin, 0)
    time.sleep(1)
    #turning on the sensor
    GPIO.output(pin, 1)
    #collect data
    vin = float(mcp.read_adc(vinPin))
    vout = float(mcp.read_adc(voutPin))
    #turning off the sensor
    GPIO.output(pin,0)
    if (vin==vout):
        return 0
    else:
        rUnknown = float(rKnown/((vin/vout)-1))
        return (rUnknown*ECCalibration)/1000
        
    
#create a CSV to save the data
def write2CSV(name,data): #appends data of sensor name given

    with open('/home/pi/'+name+'_.txt', 'w') as data_file:
        data_writer=csv.writer(data_file, delimiter=',')
        data_writer.writerow([data])

#convert the data into Json and put it onto the database
def convertAndSend(name):
  try:
    data={} #Creates an empty buffer for the data   
                        
                                      
    with open('/home/pi/'+name+'_.txt', 'r') as data_file:
                            
       csv_reader=csv.reader(data_file, delimiter=',')#reads csv file
       line_count=0   #Reads CSV file and converts it to the JSON format
       for row in csv_reader:
          data=row[0]
          line_count += 1
                                    
          result = requests.put(firebase_url + '/users/3xL6MRsUvrN7I2H134ejPGglGgr2/sensors/' + name +'.json', data=json.dumps(data))
          
          #Result Code 200 = success
          print('Record inserted. Result Code = ' + str(result.status_code) + name + ',' + result.text)
  except IOError:

    print('You fail to send the data.')
 

#returns the EC in uS/cm
def ECSensor():
    #Turning on the sensor
    GPIO.output(ECpin, 1)
    
    #collect raw data from the ADC
    vin = float(mcp.read_adc(vinPin))
    vout = float(mcp.read_adc(voutPin))
    #Turning off the sensor
    GPIO.output(ECpin, 0)
    #Open Circuit
    if (vin==vout):
        ##print("Open Circuited, will retry in 5 sec")
        ##time.sleep(5)
        return 0
    #Calculate the EC
    else:
        #Equation to find out the unknown resistance
        rUnknown = float(rKnown/((vin/vout)-1))
        ##print(rUnknown)
        #Finding the unkown conductance
        cUnknown = float((1/rUnknown)*1000)
        ##print("{:.5f}".format(cUnknown))
        #Finding the conductance per cm
        return float(cUnknown*K)
    
        #Print the value of the unknow resistance in ohms
        ##print("EC: {:.2f} mS/cm".format(EC))
    
    
#main program
while True:
    
    try:
        timeNow = datetime.today()
        ##print ("Time right Now: {}".format(timeNow))
        
        if (timeRun == 0):
            runTotalLight = totSec//(lightInterval*60)
            runTotalSensor = totSec//(sensorInterval*60)
            runTotalMister = totSec//(misterInterval*60)
            print (runTotalLight, runTotalSensor)
            #Saving the starting time of the program
            timeStart = datetime.today()
            timePassed = 0
            #callibrate the EC sensor for first time use
            ##ECCalibration = float(input("Enter the EC of Calibration solution in mS/cm or '0' for default: "))
            ##if (ECCalibration == 0):
            ##    K = .416
            ##else:
            ##    K = cellConstant(ECCalibration, ECpin)
            ##print("Cell Constant: {}".format(K))
            #calibrate the pH sensor with EC sensor submerged under solution too
            ##pHCalibration = int(input("Put the pH sensor into the solution with the EC sensor and enter '1' to proceed"))
            ##if (pHCalibration == 1):
            ##    pH0 = pHLv(pHpin)
            ##    print("pH initial = {:.2f}".format(pH0))
            ##    input("Put the EC sensor with the pH and enter '1'")
            ##    pHcal = pHConstant(pH0, pHpin)
            ##else:
            ##    break
            
        else:
            #getting the current time
            timeNow = datetime.today()
            ##print (timeNow.second)
            ##print ("Here")
            #calculate how much time have passed in seconds
            timePassed = ((timeNow.minute*60) + timeNow.second) - ((timeStart.minute*60) + timeStart.second)
            ##print (timePassed)
            if (timePassed < 0):
                timePassed = ((timeNow.minute*60) + timeNow.second) - ((timeStart.minute*60) + timeStart.second) + totSec + 1
        if (timePassed//(lightInterval*60)==timeOn):
            print ("Time right Now: {}".format(timeNow))
            print("light Condition:{}".format(lightCondition))
            #insert code to run the light sensor
            if(lightCondition == 1):
                lightCondition = 0
                GPIO.output(lightRelay, lightCondition)
            else:
                lightCondition = 1
                GPIO.output(lightRelay, lightCondition)
                
            #this is used to track how many time the light have been turn on
            timeOn = timeOn + 1
        
            if (timeOn == runTotalLight):
                timeOn = 0
            print("Lights on: {}".format(timeOn))
        
        
        #A interval of time set by the sensorInterval variable
        #Enter any code here to run it with the sensor interval
        if (timePassed//(sensorInterval*60)==timeCollected):
            #print ("Time right Now: {}".format(timeNow))
            #reads the humidity and temperature from the sensor
            #returns two decimals if the sensor can read the data,
            #returns None for both if the sensor cannot
            ##humidity0, tempC0 = Adafruit_DHT.read_retry(sensor, dhtSensor0)
            ##humidity1, tempC1 = Adafruit_DHT.read_retry(sensor, dhtSensor1)
            humidity0, tempC0 = tempAndHum(dhtSensor0)
            humidity1, tempC1 = tempAndHum(dhtSensor1)
            #print(humidity0, humidity1)
            print("hereTemp")
            #humidity1 =0.0
            #tempC1 = 0.0
            #humidity0 = float(humidity0)
            #humidity1 = float(humidity1)
            #tempC0 = float(tempC0)
            #tempC1 = float(tempC1)
            #humidity0T = round(humidity0, 2)
            #humidity1T = round(humidity1, 2)
            #tempF0 = (tempC0*1.8)+32
            #tempF1 = (tempC1*1.8)+32
            #tempC0T = round(tempF0, 2)
            #tempC1T = round(tempF1, 2)
            print("here2")

            if humidity0 is not None and tempC0 is not None:
            #.1f tells how to report the floating point number to the tenth
                print("Temp0: {:.1f} C     Humidity0: {:.1f}%".format(tempC0, humidity0))
            else:
                print("Failed to get reading for Sensor 0, Try again")
            if humidity1 is not None and tempC1 is not None:
            #.1f tells how to report the floating point number to the tenth
                print("Temp1: {:.1f} C     Humidity1: {:.1f}%".format(tempC1, humidity1))
            else:
                print("Failed to get reading for Sensor 1, Try again")
            #Getting the electrical conductivity
            EC = ECSensor()
            #ECT = round(EC, 2)
            #Getting the UV light index
            uv = uvIndex(uvPin)
            #uvT = round(uv, 3)
            
            #Find the pH
            pH = pHLv(pHpin)
            #pHT = round(pH, 2)
            print("pH: {:.2f}".format(pH))
            print ("Cell Constant: {:.2f}".format(K))
            print("EC: {:.4f}".format(EC))
            
            #find the visible, ir, and lux from the light sensor
            full, ir = visibleIr()
            lux = luxLight(full, ir)
            time.sleep(.001)
            full, ir = visibleIr()
            lux = luxLight(full, ir)
            #fullT = round(full, 2)
            #luxT = round(lux, 2)
            #irT = round(ir, 2)
            
            #Create a list that contains all the data
            data = [ EC , full, humidity0, humidity1, ir, lux, tempC0, tempC1, uv, pH]
            
            #save the data into their own seperate files and send it to the database
            for i in range(10):
                write2CSV(name[i],data[i])
                convertAndSend(name[i])
            
            #this is used to track how many time the sensors have collected data
            timeCollected = timeCollected + 1
            if (timeCollected == runTotalSensor):
                timeCollected = 0
            print("Sensors on: {}".format(timeCollected))
        
        if (timePassed//(misterInterval*60)==timeMist):
            ##print ("Time right Now: {}".format(timeNow))
            
            #insert code to run the light sensor
            GPIO.output(misterRelay, 0)
            time.sleep(1)#Mister run time
            GPIO.output(misterRelay, 1)
            GPIO.output(solutionRelay, 0)
            time.sleep(2)#perastaltic pump
            GPIO.output(solutionRelay, 1)
            
            #this is used to track how many time the light have been turn on
            timeMist = timeMist + 1
        
            if (timeMist == runTotalMister):
                timeMist = 0
            print("Mister on: {}".format(timeMist))

        #Another interval set by the lightInterval variable

        #time.sleep(1)
        #increase the timerun
        timeRun = timeRun + 1
        
        #print ("Number of time ran: {}".format(timeRun))
        
    except KeyboardInterrupt:
        GPIO.output(ECpin, 0)
        print("Exitting...")
        GPIO.cleanup()
    except BaseException as e:
        print("Something's Wrong: " + str(e))
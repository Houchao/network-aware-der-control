import pandas as pd
import numpy as np
import opendssdirect as dss

# from core import dss_function

# Author: Houchao Gan
from datetime import timedelta, datetime

ELEMENT_CLASSES = {
    'Load': dss.Loads,
    'PV': dss.PVsystems,
    'Generator': dss.Generators,
    'Line': dss.Lines,
    'Xfmr': dss.Transformers,
}
LINE_CLASSES = ['Line', 'Xfmr']


class OpenDSSException(Exception):
    pass


class OpenDSS:
    def __init__(self, dss_file, **kwargs):

        print('DSS Compiling...')
        print(dss_file)

        self.run_command("Compile " + dss_file)
        
        # Run redirect files after main de:
            # if not isinstance(redirss file

        # if redirects_post is not Nonects_post, list):
                # redirects_post = [redirects_post]
            # for redirect in redirects_post:
                # print(redirect)
                # self.redirect(redirect)
      
        # check if elements exist. If storage exists, save storage names
        a = ELEMENT_CLASSES["Generator"]

        self.includes_elements = {class_name: len(ELEMENT_CLASSES[class_name].AllNames()) > 0 for class_name in 
                                   ['Load', 'PV', 'Generator']}                                   
        storages = self.get_all_elements('Storage') 
        if len(storages):
            print('have stroage')
            self.includes_elements['Storage'] = True 
            self.storage_names = storages.index.to_list() 
        else: 
            print('no storage')
            self.includes_elements['Storage'] = False 
            self.storage_names = [] 
      
        print('included elements')
        print(self.includes_elements)

        self.run_dss()
        print('DSS Compiled Circuit:', dss.Circuit.Name())

        #AllNodeNames = dss.Circuit.YNodeOrder()
        #AllNodeNames = pd.DataFrame(AllNodeNames)
        #AllNodeNames.to_csv('AllNodeNames.csv')

    def Circuit_AllNodeNames(self):
        return dss.Circuit.AllNodeNames()

    def Circuit_AllBusMagPu(self):
        return dss.Circuit.AllBusMagPu()

    def Circuit_AllBusVMag(self):
        return dss.Circuit.AllBusVmag()  # Note: lowercase 'm' in opendssdirect

    def Circuit_AllBusVolts(self):
        return dss.Circuit.AllBusVolts()  # This is the correct one for complex voltages

    # Add this if you want pu magnitudes too (optional)
    def Circuit_AllBusVMagPu(self):
        return dss.Circuit.AllBusVMagPu()
        
    @staticmethod# use this to omit self, otherwise "def run_command(self,cmd):"
    def run_command(cmd):
        status = dss.Text.Command(cmd)
        if status:
            print('DSS Status ({}): {}'.format(cmd, status))

    def redirect(self, filename):
        self.run_command('Redirect ' + filename)

    @staticmethod
    def run_dss(no_controls=False):
        if no_controls:
            status = dss.Solution.SolveNoControl()
        else:
           status = dss.Solution.Solve()
        if status:
            print('DSS Solve Status: {}'.format(status))

    # GET METHODS

    @staticmethod
    def get_all_buses():
        return dss.Circuit.AllBusNames()

    @staticmethod
    def get_all_elements(element='Load'):
        if element in ELEMENT_CLASSES:
            cls = ELEMENT_CLASSES[element]
            df = dss.utils.to_dataframe(cls)
        else:
            df = dss.utils.class_to_dataframe(element, transform_string=lambda x: pd.to_numeric(x, errors='ignore'))
            # df = dss.utils.class_to_dataframe(element)
        return df

    @staticmethod
    def get_circuit_power():
        # returns negative of circuit power (positive = consuming power)
        powers = dss.Circuit.TotalPower()
        if len(powers) == 2:
            p, q = tuple(powers)
            return -p, -q
        elif len(powers) == 6:
            p = powers[0:2:]
            q = powers[1:2:]
            return -p, -q
        else:
            raise OpenDSSException('Expected 1- or 3-phase circuit')

    @staticmethod
    def get_losses():
        p, q = dss.Circuit.Losses()
        return p / 1000, q / 1000

    # def get_circuit_info(self):
        # # TODO: Add powers by phase if 3-phase; options to add/remove element classes
        # p_total, q_total = self.get_circuit_power()
        # p_loss, q_loss = self.get_losses()
        # p_load, q_load = self.get_total_power()
        # p_pv, q_pv = self.get_total_power(element='PV')
        # p_gen, q_gen = self.get_total_power(element='Generator')
        # p_stor, q_stor = self.get_total_power(element='Storage')
        # return {
            # 'Total P (MW)': p_total / 1000,
            # 'Total Q (MVAR)': q_total / 1000,
            # 'Total Loss P (MW)': p_loss / 1000,
            # 'Total Loss Q (MVAR)': q_loss / 1000,
            # 'Total Load P (MW)': p_load / 1000,
            # 'Total Load Q (MVAR)': q_load / 1000,
            # 'Total PV P (MW)': p_pv / 1000,
            # 'Total PV Q (MVAR)': q_pv / 1000,
            # 'Total Generators P (MW)': p_gen / 1000,
            # 'Total Generators Q (MVAR)': q_gen / 1000,
            # 'Total Storage P (MW)': p_stor / 1000,
            # 'Total Storage Q (MVAR)': q_stor / 1000,
        # }

    def get_circuit_info(self): 
         # TODO: Add powers by phase if 3-phase; options to add/remove element classes 
        p_total, q_total = self.get_circuit_power() 
        p_loss, q_loss = self.get_losses() 
        total_by_class = {class_name: self.get_total_power(class_name) for class_name, included in 
                           self.includes_elements.items() if included} 
 
 
        out = {'Total P (MW)': p_total / 1000, 
                'Total Loss P (MW)': p_loss / 1000, 
               } 
               
        for class_name, (p, q) in total_by_class.items(): 
            if class_name=='Generator':
               p=-p          
            out['Total {} P (MW)'.format(class_name)] = p / 1000 
            
 
 
        out.update({'Total Q (MVAR)': q_total / 1000, 
                     'Total Loss Q (MVAR)': q_loss / 1000, 
                     }) 
        for class_name, (p, q) in total_by_class.items(): 
            if class_name=='Generator':
               q=-q    
            out['Total {} Q (MVAR)'.format(class_name)] = q / 1000 
 
 
        return out 

    def get_P(self, name, element='Load',total=False):
        # If phase=<int>, return length-2 tuple (Pa, Qa) or length-4 tuple (P1a, Q1a, P2a, Q2a), for Lines
        # If phase=None and total=False, return length-2*n_phases, or length-4*n_phases for Lines
        # If phase=None and total=True, return length-2 tuple (Pa+Pb+Pc, Qa+Qb+Qc)
        self.set_element(name, element)
        powers = dss.CktElement.Powers()
        if total:
            powers = [p for i, p in enumerate(powers) if i % 4 in [0, 1]]
            p = sum(powers[0::2])
            return p
        else:
            if element not in LINE_CLASSES:
                powers = powers[:-2]
                p=powers[0::2]
            return p


    def get_power(self, name, element='Load', phase=None, total=False):
        # If phase=<int>, return length-2 tuple (Pa, Qa) or length-4 tuple (P1a, Q1a, P2a, Q2a), for Lines
        # If phase=None and total=False, return length-2*n_phases, or length-4*n_phases for Lines
        # If phase=None and total=True, return length-2 tuple (Pa+Pb+Pc, Qa+Qb+Qc)
        self.set_element(name, element)
        powers = dss.CktElement.Powers()
        if phase is None:
            if total:
                #powers = [p for i, p in enumerate(powers) if i % 4 in [0, 1]]
                powers = [p for i, p in enumerate(powers) if i<len(powers)-2]
                p = sum(powers[0::2])
                q = sum(powers[1::2])
                return p,q
            else:
                if element not in LINE_CLASSES:
                    powers = powers[:-2]
                p=powers[0::2]
                q=powers[1::2]
                return p,q

        elif phase - 1 in range(len(powers) // 4):
            powers = powers[4 * (phase - 1):4 * phase]
            if element not in LINE_CLASSES:
                powers = powers[:2]
            return tuple(powers)
        else:
            raise OpenDSSException('Bad phase for {} {}: {}'.format(element, name, phase))

    # TODO: alternative to above, not yet tested (need to check for 3 phase loads and lines)
    # def get_p_q(self, name, element='Load', bus=1):
    #     self.set_element(name, element)
    #     cls = ELEMENT_CLASSES[element]
    #     try:
    #         p, q = cls.kW(), cls.kvar()
    #         return p, q
    #     except:
    #         # Need to find the correct exception
    #         return self.get_power(name, element, bus)

    def get_total_power(self, element='Load'):
        p_total, q_total = 0, 0
        if element in ELEMENT_CLASSES:
            cls = ELEMENT_CLASSES[element]
            all_names = cls.AllNames()
            for name in all_names:
                p, q = self.get_power(name, element, total=True)
                p_total += p
                q_total += q
        elif element == 'Storage' and self.includes_elements['Storage']: 
             # reversing sign for storage 
            storage_p = [-self.get_property(name, 'kW', 'Storage') for name in self.storage_names] 
            storage_q = [-self.get_property(name, 'kvar', 'Storage') for name in self.storage_names] 
            p_total = sum(storage_p) 
            q_total = sum(storage_q) 
            # print('storage_p:',p_total)
            # print('storage_q:',q_total)

        return p_total, q_total


    def get_bus_voltage_magonly_pu_polar_1phase(self,bus,phase):
        dss.Circuit.SetActiveBus(bus)
        v=dss.Bus.VMagAngle()
        vpu = dss.Bus.puVmagAngle()
        if len(v) == 4:  # remove zeros for single phase voltage
            v = v[:2]
            vpu=vpu[:2]
        if any([x <= 0 for x in v[::2]]):
            print(bus)
            print(v[0])
            print(v[2])
            raise OpenDSSException('Bus "{}" voltage = {}, out of bounds'.format(bus, v))
        v = v[::2]
        vpu=vpu[::2]
        
        # select phase
        if len(v) % 3 == 0:  # 3 phase bus
            l = len(v) // 3
            v = v[l*(phase-1): l*phase]
            vpu=vpu[l*(phase-1): l*phase]
        # if len(v) == 1:
            # return v[0]
        # else:
# #            return tuple(v)
            # return v
        return v,vpu

    def get_bus_voltage_magonly_pu_polar(self,bus):
        dss.Circuit.SetActiveBus(bus)
        v=dss.Bus.VMagAngle()
        vpu = dss.Bus.puVmagAngle()
        if any([x <= 0 for x in v[::2]]):
            print(bus)
            print(v[0])
            print(v[2])
            raise OpenDSSException('Bus "{}" voltage = {}, out of bounds'.format(bus, v))
        v = v[::2]
        vpu=vpu[::2]
        
        return v,vpu

    @staticmethod
    def get_bus_voltage(bus, phase=None, pu=True, polar=True, mag_only=True):
        dss.Circuit.SetActiveBus(bus)
        if polar:
            if pu:
                v = dss.Bus.puVmagAngle()
            else:
                v = dss.Bus.VMagAngle()
            if len(v) == 4:  # remove zeros for single phase voltage
                v = v[:2]
            if any([x < 0 for x in v[::2]]):
                print(bus)
                print(v[0])
                #print(v[2])
                raise OpenDSSException('Bus "{}" voltage = {}, out of bounds'.format(bus, v))
            if mag_only:  # remove angles
                v = v[::2]
        else:
            if pu:
                v = dss.Bus.PuVoltage()
            else:
                v = dss.Bus.Voltages()
        
        if phase is not None and len(v) % 3 == 0:  # 3 phase bus
            l = len(v) // 3
            v = v[l*(phase-1): l*phase]

        if len(v) == 1:
            return v[0]
        else:
            return tuple(v)
            #return v



    def get_voltage(self, name, element='Load', **kwargs):
        # note: for lines/transformers, always takes voltage from Bus1
        self.set_element(name, element)
        bus = dss.CktElement.BusNames()[0]
        return self.get_bus_voltage(bus, **kwargs)
        

    def get_all_complex(self, name, element='Load'):
        self.set_element(name, element)
        return {
            'Voltages': dss.CktElement.Voltages(),
            'VoltagesMagAng': dss.CktElement.VoltagesMagAng(),
            'Currents': dss.CktElement.Currents(),
            'CurrentsMagAng': dss.CktElement.CurrentsMagAng(),
            'Powers': dss.CktElement.Powers(),
        }
        

    def get_property(self, name, property_name, element='Load'): 
        # print('s1')
        #print('storage_name',name)
        self.set_element(name, element) 
        # print('s2')
        all_properties = dss.Element.AllPropertyNames() 
        # print('s3')
        if property_name not in all_properties: 
            # print('s4')
            raise OpenDSSException('Could not find {} property for {} "{}"'.format(property_name, element, name)) 
 
        # print('s5')
        idx = all_properties.index(property_name) 
        value = dss.Properties.Value(str(idx + 1)) 
        
        try: 
            number = float(value) 
            return number 
        except ValueError: 
            return value 
            
    def get_NumBues(self):
        return dss.Circuit.NumBuses()

    def get_Ymatrix(self, show_y=True, phase='ABC'):
    
        self.run_command('vsource.source.enabled=no')
        self.run_command('batchedit Generator..* enabled=no')
        self.run_command('batchedit Load..* enabled=no')
        #self.run_command('batchedit Transformer..* enabled=no')
        self.run_command('solve')
        
        if show_y:
            self.run_command('show Y')
        
        base_y = np.array(dss.Circuit.SystemY())
        #print(base_y)
        
        YNodeNames = dss.Circuit.YNodeOrder()
        #print(YNodeNames)
        
        YNodeNames = np.array([str(node) for node in YNodeNames])
        
        Y_tmp = base_y.reshape([len(YNodeNames), len(YNodeNames)*2])
        #print(Y_tmp.shape)
        #Ymatrix = Ymatrix.T
        #print(Y_tmp[0, :])
        [row, col] = Y_tmp.shape
        
        Ymatrix = Y_tmp[:, range(0, col, 2)] + 1j*Y_tmp[:, range(1, col, 2)]
        [row, col] = Ymatrix.shape
        
        #print(Ymatrix.shape)
        #print(Ymatrix)
        #print(col)
                
        self.run_command('vsource.source.enabled=yes')
        self.run_command('batchedit Generator..* enabled=yes')
        self.run_command('batchedit load..* enabled=yes')
        #self.run_command('batchedit Transformer..* enabled=yes')
        self.run_command('solve')
        
        #print(YNodeNames)
        #print(dss.Circuit.NumBuses())
        #index = []
        
        #for loadName in loadNode:      
        #    index.append(YNodeNames.index(loadName + '.' + str(phase)))
        
        # prepare Y matrix output to a file
        YNodeNames = YNodeNames.reshape([len(YNodeNames), 1])
        
        if phase == 'A' or phase == 'a':
            Y_dss = np.copy(Ymatrix[range(0, row, 3), :])
            Y_dss = Y_dss[:, range(0, col, 3)]
            
            YNodeNames = YNodeNames[range(0, len(YNodeNames), 3), :]
        elif phase == 'B' or phase == 'b':
            Y_dss = np.copy(Ymatrix[range(1, row, 3), :])
            Y_dss = Y_dss[:, range(1, col, 3)]
            
            YNodeNames = YNodeNames[range(0, len(YNodeNames), 3), :]
        elif phase == 'C' or phase == 'c':
            Y_dss = np.copy(Ymatrix[range(2, row, 3), :])
            Y_dss = Y_dss[:, range(2, col, 3)]
            
            YNodeNames = YNodeNames[range(0, len(YNodeNames), 3), :]
        else:
            Y_dss = np.copy(Ymatrix)
        
        #order_nodes = []
        #for node_num in range(len(YNodeNames)):
        #    order_nodes.append(node_num)
        
        # only need first phase
        #YNodeNames = YNodeNames[range(0, len(YNodeNames), 3), :]
        
        # Y matrix need be flip to make sure T1 is at beginning   
        #print(order_nodes)
        AllNodeNamesYOrder = np.copy(YNodeNames)

        #print(YNodeNames.shape)
        
        Y_out = np.concatenate([YNodeNames, Y_dss], axis=1)       
        #print(Y_out.shape)
        
        YNodeNames = np.insert(YNodeNames.T, 0, 0)
        YNodeNames = YNodeNames.reshape([1, len(YNodeNames.T)]) 
        #print(YNodeNames.shape)
        
        Y_out = np.concatenate([YNodeNames, Y_out], axis=0)
        
        np.savetxt('Y_dss.csv', Y_out, delimiter=',', fmt='%s')
        
        Nnode = dss.Circuit.NumBuses()
        print(Nnode)
        #self.allNodeNames = self.feeder.get_YnodeNames()
        AllNodeNamesYOrder = AllNodeNamesYOrder.reshape(Nnode)
        AllNodeNamesYOrder = AllNodeNamesYOrder.tolist()
        
        for idx, bus_name in enumerate(AllNodeNamesYOrder):
            bus_name = bus_name.split('.')[0]
            AllNodeNamesYOrder[idx] = bus_name.lower()

        #print(AllNodeNamesYOrder)
        return Y_dss, AllNodeNamesYOrder

    def get_kvBase(self, bus):
        dss.Circuit.SetActiveBus(bus)
        return dss.Bus.kVBase() * np.sqrt(3) * 1000
    # SET METHODS
    # @staticmethod
    # def set_element(name, element):
        # # dss.Circuit.SetActiveElement(self.__Class + '.' + self.__Name)
        # if element=='Storage':
           # print('storage name: {}'.format(name))
           # print('storage name_lower case: {}'.format(name.lower()))
           # cls=ELEMENT_CLASSES[element]
           # print(cls)
        # name = name.lower()
        # cls = ELEMENT_CLASSES[element]
        # cls.Name(name)

        # if cls.Name() != name:
            # raise OpenDSSException('{} "{}" does not exist'.format(element, name))

    @staticmethod 
    def set_element(name, element): 
        # dss.Circuit.SetActiveElement(self.__Class + '.' + self.__Name) 
        name = name.lower() 
        if element in ELEMENT_CLASSES: 
            cls = ELEMENT_CLASSES[element] 
        else: 
            dss.Circuit.SetActiveClass(element) 
            cls = dss.ActiveClass 
            name=name.split('.')[1]
        cls.Name(name) 

        if cls.Name() != name: 
            raise OpenDSSException('{} "{}" does not exist'.format(element, name)) 


    def set_power(self, name, p=None, q=None, element='Load', size=None):
        if element in ELEMENT_CLASSES:
            self.set_element(name, element)
            cls = ELEMENT_CLASSES[element]
            if p is not None:
                cls.kW(p)
            if q is not None:
                cls.kvar(q)
        elif element == 'Storage':
            if p > 0:  # charge
                self.run_command('{}.{}.state=charging %charge={}'.format(element, name, abs(p) / size * 100))
            elif p < 0:  # discharge
                self.run_command('{}.{}.state=discharging %discharge={}'.format(element, name, abs(p) / size * 100))
            else:  # idle
                self.run_command('{}.{}.state=idling'.format(element, name))
        else:
            raise OpenDSSException("Unknown element class:", element)

    @staticmethod
    def set_tap(name, tap, max_tap=16):
        dss.RegControls.Name(name)
        tap = min(max(int(tap), -max_tap), max_tap)
        dss.RegControls.TapNumber(tap)

    @staticmethod
    def get_tap(name):
        dss.RegControls.Name(name)
        return int(dss.RegControls.TapNumber())

    def get_allbus_phase1_complex_kv(self, num_buses=None, phase=3):
        """
        Robust version: Handles potential NaNs/zeros in AllBusVolts by querying each bus individually.
        Returns complex phase-A voltages in kV for ALL buses (one per bus).
        Matches MATLAB V_hat exactly.
        """
        if num_buses is None:
            num_buses = self.get_NumBues()

        buses = self.get_all_buses()
        if len(buses) != num_buses:
            raise OpenDSSException(f"Expected {num_buses} buses, got {len(buses)}")

        V_hat = np.zeros(num_buses, dtype=complex)

        for i, bus_name in enumerate(buses):
            dss.Circuit.SetActiveBus(bus_name)
            vmag_ang = np.array(dss.Bus.puVmagAngle())
            # puVmagAngle returns [mag1, ang1, mag2, ang2, ...] in pu, degrees
            # For single-phase or delta buses, it may have fewer entries
            # We take the first non-zero magnitude (phase A equivalent)
            mags = vmag_ang[::2]
            angs = vmag_ang[1::2]

            # Find first valid phase (mag > 0)
            valid_idx = np.where(mags > 1e-6)[0]
            if len(valid_idx) == 0:
                raise OpenDSSException(f"Bus {bus_name} has no valid voltage (all mags <= 0)")

            first_phase_idx = valid_idx[0]
            mag_pu = mags[first_phase_idx]
            ang_deg = angs[first_phase_idx]

            V_hat[i] = mag_pu * np.exp(1j * np.deg2rad(ang_deg)) * (
                        4.8 / np.sqrt(3))  # convert pu to kV (phase-neutral base)

        return V_hat

    def get_v0_from_first_element(self):
        """
        Returns complex source voltage V0 in kV (same as MATLAB:
        V0_complex = complex(cktElement.Voltages(1:2:end), cktElement.Voltages(2:2:end))
        Then takes first value (phase A).
        """
        # First element is always the voltage source
        element_names = dss.Circuit.AllElementNames()
        if not element_names:
            raise OpenDSSException("No elements in circuit")
        self.set_element(element_names[0], element="Vsource")
        volts = np.array(dss.CktElement.Voltages())
        complex_volts = (volts[0::2] + 1j * volts[1::2]) * 1e-3  # kV
        return complex_volts[0]  # phase A



# def save_linear_power_flow(**kwargs):
#     AllNodeNames, Vbase_allnode, node_number = dss_function.get_node_information(dss)
#     _ = dss_function.system_topology_matrix_form(dss, AllNodeNames, **kwargs)


if __name__ == "__main__":
    #from constants import master_dssfile, load_dssfile_all, pv_dssfile, storage_dssfile, freq_all, start_time

    master_dssfile = "ieee37.dss"
    load_dssfile_all = "load.dss"
    pv_dssfile = "pv.dss"

    freq_all = timedelta(seconds=1)
    start_time = datetime(2020, 7, 1, 11, 00)
    duration = timedelta(hours=1)
    end_time = start_time + duration

    d = OpenDSS(master_dssfile)
    #d.redirect(storage_dssfile)
    d.run_command('Solve mode=snap')
    d.run_command('Set mode=daily stepsize=1s number=1')

    # print('run output:', d.run_dss())
    # print()

    # check circuit functions
    print('circuit info:')
    info = d.get_circuit_info()
    for key, val in info.items():
        print(key, val)
    print()

    # All Element Names
    print('DSS Elements: ', dss.Circuit.AllElementNames())

    P0_hat, _ = d.get_circuit_power()

    # All Loads, as dataframe
    df_loads = d.get_all_elements()
    print('First 5 Loads (DataFrame)')
    print(df_loads.head())

    # All Storages, as dataframe
    df_storage = d.get_all_elements('Storage')
    print('First 5 Storages (DataFrame)')
    print(df_storage.head())

    # check bus voltages
    buses = d.get_all_buses()
    bus0 = buses[0]
    print('First Bus voltage:', d.get_bus_voltage(buses[0]))
    print('First Bus voltage, phase1:', d.get_bus_voltage(buses[0], phase=1))
    print('First Bus voltage, complex:', d.get_bus_voltage(buses[0], polar=False, pu=False))
    print('First Bus voltage, MagAng:', d.get_bus_voltage(buses[0], mag_only=False))

    # check load functions
    load_names = d.get_all_elements().index
    print('Load {} data: {}'.format(load_names[0], d.get_all_complex(load_names[0])))
    print('load voltage:', d.get_voltage(load_names[0]))
    print('load powers:', d.get_power(load_names[0]))
    print()

    pv_names = d.get_all_elements("Generator").index
    # checking setting load power
    d.set_power(pv_names[0], p=1000, element="Generator")
    d.run_dss()
    print('PV {} data: {}'.format(pv_names[0], d.get_all_complex(pv_names[0], element="Generator")))
    print('PV voltage:', d.get_voltage(pv_names[0], element="Generator"))
    print('PV powers:', d.get_power(pv_names[0], element="Generator"))

    P0_hat_1, _ = d.get_circuit_power()

    d.run_dss()

    P0_hat_2, _ = d.get_circuit_power()

    d.run_dss()

    P0_hat_3, _ = d.get_circuit_power()





    # check line functions
    # line = 'pc-28179'
    # print('Line powers:', d.get_power(line, element='Line'))
    # print('Line voltages:', d.get_voltage(line, element='Line'))
    print("done")

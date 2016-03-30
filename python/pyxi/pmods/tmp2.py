#   Copyright (c) 2016, Xilinx, Inc.
#   All rights reserved.
# 
#   Redistribution and use in source and binary forms, with or without 
#   modification, are permitted provided that the following conditions are met:
#
#   1.  Redistributions of source code must retain the above copyright notice, 
#       this list of conditions and the following disclaimer.
#
#   2.  Redistributions in binary form must reproduce the above copyright 
#       notice, this list of conditions and the following disclaimer in the 
#       documentation and/or other materials provided with the distribution.
#
#   3.  Neither the name of the copyright holder nor the names of its 
#       contributors may be used to endorse or promote products derived from 
#       this software without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
#   THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
#   PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
#   CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, 
#   EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
#   PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
#   OR BUSINESS INTERRUPTION). HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
#   WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
#   OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF 
#   ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

__author__      = "Cathal McCabe, Yun Rock Qu"
__copyright__   = "Copyright 2016, Xilinx"
__email__       = "xpp_support@xilinx.com"


import time
from . import _iop
from . import pmod_const
from pyxi import MMIO
from pyxi import Overlay

PROGRAM = "tmp2.bin"

class TMP2(object):
    """This class controls a temperature sensor PMOD.

    Attributes
    ----------
    iop : _IOP
        I/O processor instance used by TMP2
    mmio : MMIO
        Memory-mapped I/O instance to read and write instructions and data.
    log_ms : int
        The length of the log in milliseconds, for debug only.
        
    """
    def __init__(self,pmod_id):
        """Return a new instance of a TMP2 object. 
        
        When we call request_iop(), an exception might be raised if 
        the *force* flag is not set. Please refer to _iop.request_iop() for 
        additional details.
    
        Note
        ----
        The pmod_id 0 is reserved for XADC (JA).
        
        Parameters
        ----------
        pmod_id : int
            The PMOD ID (1, 2, 3, 4) corresponding to (JB, JC, JD, JE).
            
        """
        self.iop = _iop.request_iop(pmod_id, PROGRAM)
        self.mmio = MMIO(self.iop.base_addr, pmod_const.IOP_MMIO_REGSIZE)
        self.log_ms = 0
        
        self.iop.start()

    def read(self):
        """Read current temperature value measured by the TMP2 PMOD.
        
        Parameters
        ----------
        None
        
        Returns
        -------
        float
            The current sensor value.
        
        """
        self.mmio.write(pmod_const.MAILBOX_OFFSET+\
                        pmod_const.MAILBOX_PY2IOP_CMD_OFFSET, 3)      
        while (self.mmio.read(pmod_const.MAILBOX_OFFSET+\
                                pmod_const.MAILBOX_PY2IOP_CMD_OFFSET) == 3):
            pass
        self.value = self.mmio.read(pmod_const.MAILBOX_OFFSET)
        return self._reg2float(self.value)

    def set_log_ms(self,log_ms):
        """Set the length of the log in the TMP2 PMOD.
        
        This method can set the length of the log, so that users can read out
        multiple values in a single log. 
        
        Parameters
        ----------
        log_ms : int
            The length of the log in milliseconds, for debug only.
            
        Returns
        -------
        None
        
        """
        if (log_ms < 0):
            raise ValueError("Log length should not be less than 0.")
        self.log_ms = log_ms
        self.mmio.write(pmod_const.MAILBOX_OFFSET+4, self.log_ms)

    def start_log(self, log_ms=0):
        """Start recording multiple values in a log.
        
        This method will first call set_log_ms() before writting to the MMIO.
        
        Parameters
        ----------
        log_ms : int
            The length of the log in milliseconds, for debug only.
            
        Returns
        -------
        None
        
        """
        self.set_log_ms(log_ms)
        self.mmio.write(pmod_const.MAILBOX_OFFSET+\
                        pmod_const.MAILBOX_PY2IOP_CMD_OFFSET, 7)

    def stop_log(self):
        """Stop recording multiple values in a log.
        
        Simply write to the MMIO to stop the log.
        
        Parameters
        ----------
        None
            
        Returns
        -------
        None
        
        """
        self.mmio.write(pmod_const.MAILBOX_OFFSET+\
                        pmod_const.MAILBOX_PY2IOP_CMD_OFFSET, 1)    

    def print_log(self):
        """Read and print all the data in the log from mailbox.
        
        This method should only be used for debug. To get an value from the 
        TMP2 PMOD, use read() instead.
        
        Parameters
        ----------
        None
            
        Returns
        -------
        None
        
        """
        #: First stop logging
        self.stop_log()
        end_ptr = self.mmio.read(pmod_const.MAILBOX_OFFSET+8)

        if(end_ptr>=1000): 
            #: Mailbox full because end_ptr has looped, so print 1000 values
            current_ptr = end_ptr-999
            end_ptr = end_ptr-1000
            count = 1000
        else: 
            #: Mailbox not full, print to the end_ptr
            current_ptr = 0 
            count = end_ptr

        print("T\tData")
        for x in range(count):
            temp = self.mmio.read(pmod_const.MAILBOX_OFFSET+(3+x)*4)
            print(str(x) + "\t" + str(self.reg2float(temp)))
            if(current_ptr<999):
                current_ptr+=1
            else:
                current_ptr=0
      
    def _reg2float(self, reg):
        """Translate the register value to a floating-point number.
        
        Note
        ----
        The float precision is specified to be 1 digit after the decimal 
        point.
        
        Bit [31]    (1 bit)        ->    Sign (S)
        Bit [30:23] (8 bits)       ->    Exponent (E)
        Bit [22:0]  (23 bits)      ->    Mantissa (M)
        
        Parameters
        ----------
        reg : int
            A 4-byte integer.
            
        Returns
        -------
        float
            The floating-point number translated from the input.
            
        """
        if reg == 0:
            return 0.0
        sign = (reg & 0x80000000) >> 31 & 0x01
        exp = ((reg & 0x7f800000) >> 23)-127
        if (exp == 0):
            man = (reg & 0x007fffff)/pow(2,23)
        else:
            man = 1+(reg & 0x007fffff)/pow(2,23)
        result = pow(2,exp)*(man)*((sign*-2) +1)
        return float("{0:.1f}".format(result))

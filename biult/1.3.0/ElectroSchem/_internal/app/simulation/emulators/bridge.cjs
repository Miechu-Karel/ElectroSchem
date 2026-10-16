// Lokalny protokół JSON-lines. Firmware jest danymi dla emulatora CPU,
// nigdy kodem JavaScript wykonywanym przez eval/require.
'use strict';
const fs = require('fs');
const readline = require('readline');
let machine = null, serial = '', warnings = [], i2c = [], i2cAddresses = [], slave = -1;
const emit = data => process.stdout.write(JSON.stringify(data) + '\n');
const byte = b => { if (serial.length < 4096) serial += String.fromCharCode(b); };

function loadHex(text, memory) {
  let base = 0, eof = false, count = 0;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    if (eof || !/^:[0-9a-f]+$/i.test(line) || line.length % 2 !== 1) throw Error('Invalid Intel HEX record');
    const record = Buffer.from(line.slice(1), 'hex');
    if (record.length < 5 || record.length !== record[0]+5 || record.reduce((a,b)=>a+b,0)%256) throw Error('Invalid HEX checksum/length');
    const address = record.readUInt16BE(1), type = record[3], data = record.subarray(4,-1);
    if (type === 0) {
      const target = base+address;
      if (target+data.length > memory.length) throw Error('Firmware exceeds ATmega328P flash');
      memory.set(data,target); count += data.length;
    } else if (type === 1 && !data.length) eof = true;
    else if (type === 4 && data.length === 2) base = data.readUInt16BE()*65536;
    else if (type === 2 && data.length === 2) base = data.readUInt16BE()*16;
    else if (type !== 3 && type !== 5) throw Error('Unsupported HEX record');
  }
  if (!eof || !count) throw Error('Incomplete/empty HEX');
}

function loadUF2(data, memory) {
  if (!data.length || data.length%512) throw Error('Invalid UF2 length');
  const seen = new Set(), expected = data.length/512;
  for (let offset=0; offset<data.length; offset+=512) {
    const b = data.subarray(offset,offset+512);
    if (b.readUInt32LE(0)!==0x0a324655 || b.readUInt32LE(4)!==0x9e5d5157 || b.readUInt32LE(508)!==0x0ab16f30) throw Error('Invalid UF2 magic');
    const flags=b.readUInt32LE(8), address=b.readUInt32LE(12)-0x10000000, size=b.readUInt32LE(16), index=b.readUInt32LE(20);
    if (flags&1 || flags&0x1000 || !(flags&0x2000) || b.readUInt32LE(28)!==0xe48bff56) throw Error('UF2 is not RP2040 firmware');
    if (!size || size>476 || address<0 || address+size>memory.length || seen.has(index) || index>=expected || b.readUInt32LE(24)!==expected) throw Error('Invalid UF2 block/address');
    seen.add(index); memory.set(b.subarray(32,32+size),address);
  }
}

function init(engine, filename, bootrom) {
  if (!fs.statSync(filename).isFile() || fs.statSync(filename).size>16*1024*1024) throw Error('Firmware must be a file smaller than 16 MiB');
  const firmware = fs.readFileSync(filename);
  serial = ''; warnings=[];
  if (engine==='avr8js') {
    const avr=require('avr8js'), flash=new Uint8Array(32768);
    loadHex(firmware.toString('utf8'),flash);
    const cpu=new avr.CPU(new Uint16Array(flash.buffer),2048);
    const ports={B:new avr.AVRIOPort(cpu,avr.portBConfig), C:new avr.AVRIOPort(cpu,avr.portCConfig), D:new avr.AVRIOPort(cpu,avr.portDConfig)};
    for (const config of [avr.timer0Config,avr.timer1Config,avr.timer2Config]) new avr.AVRTimer(cpu,config);
    new avr.AVREEPROM(cpu,new avr.EEPROMMemoryBackend(1024));
    const adc=new avr.AVRADC(cpu,avr.adcConfig);
    adc.onADCRead=()=>{throw Error('ADC circuit coupling is not implemented in this alpha');};
    const uart=new avr.AVRUSART(cpu,avr.usart0Config,16000000); uart.onByteTransmit=byte;
    const twi=new avr.AVRTWI(cpu,avr.twiConfig,16000000);
    twi.eventHandler={
      start(){twi.completeStart();}, stop(){slave=-1;twi.completeStop();},
      connectToSlave(address,write){slave=address;twi.completeConnect(write && i2cAddresses.includes(address));},
      writeByte(value){if(i2c.length>=1024)throw Error('I2C transaction limit exceeded');i2c.push([slave,value]);twi.completeWrite(true);},
      readByte(){throw Error('I2C reads are not integrated');}
    };
    const mapping={};
    for (let i=0;i<14;i++) mapping['D'+i]=[i<8?'D':'B',i<8?i:i-8];
    for (let i=0;i<6;i++) mapping['A'+i]=['C',i];
    machine={
      step(seconds,inputs) {
        for (const [key,value] of Object.entries(inputs)) if (mapping[key]) { const [p,n]=mapping[key]; ports[p].setPin(n,!!value); }
        const end=cpu.cycles+Math.round(seconds*16000000);
        while(cpu.cycles<end) { avr.avrInstruction(cpu); cpu.tick(); }
      },
      state() { return {time:cpu.cycles/16000000,gpio:Object.fromEntries(Object.entries(mapping).map(([k,[p,n]])=>[k,ports[p].pinState(n)])),pc:cpu.pc}; }
    };
  } else if (engine==='rp2040js') {
    const {Simulator}=require('rp2040js'), sim=new Simulator(), mcu=sim.rp2040;
    mcu.logger={debug(){},info(){},warn(...args){if(warnings.length<8) warnings.push(args.join(' '));},error(...args){throw Error(args.join(' '));}};
    if (bootrom) {
      if (!fs.statSync(bootrom).isFile() || fs.statSync(bootrom).size!==16384) throw Error('RP2040 boot ROM must be a 16 KiB binary');
      const bytes=fs.readFileSync(bootrom);
      mcu.loadBootrom(new Uint32Array(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length)));
    } else {
      // Bare-metal może nie potrzebować ROM. Każdy faktyczny dostęp do
      // niego bez pliku kończy się błędem, a nie fałszywą wartością zero.
      for (const method of ['readUint8','readUint16','readUint32']) {
        const original=mcu[method].bind(mcu);
        mcu[method]=address=>{
          if((address>>>0)<16384) throw Error('Firmware requires RP2040 boot ROM: assign a legally obtained 16 KiB ROM binary');
          return original(address);
        };
      }
      mcu.core.SP=0x20042000;
    }
    loadUF2(firmware,mcu.flash);
    mcu.core.PC=0x10000000;
    mcu.onBreak=()=>{throw Error('Firmware breakpoint / unsupported instruction');};
    mcu.uart[0].onByte=byte;
    machine={
      step(seconds,inputs) {
        for(const [key,value] of Object.entries(inputs)) {
          const match=/^GP(\d+)$/.exec(key);
          if(match && Number(match[1])<30) mcu.gpio[Number(match[1])].setInputValue(!!value);
        }
        const end=sim.clock.nanos+seconds*1e9;
        while(sim.clock.nanos<end) {
          if(mcu.core.waiting) sim.clock.tick(Math.min(end-sim.clock.nanos,sim.clock.nanosToNextAlarm));
          else sim.clock.tick(Math.max(1,mcu.core.executeInstruction())*1e9/mcu.clkSys);
        }
      },
      state() {return {time:sim.clock.nanos/1e9,gpio:Object.fromEntries(mcu.gpio.slice(0,30).map((p,i)=>['GP'+i,p.value])),pc:mcu.core.PC};}
    };
  } else throw Error('Unsupported engine');
  return machine.state();
}

readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line',line=>{
  try {
    if(line.length>65536) throw Error('Request too large');
    const request=JSON.parse(line);
    if(request.op==='init') emit({ok:true,...init(request.engine,request.firmware,request.bootrom)});
    else if(request.op==='step') {
      if(!machine) throw Error('Load firmware first');
      if(!Number.isFinite(request.seconds) || request.seconds<=0 || request.seconds>.02) throw Error('Invalid time slice');
      i2cAddresses=request.i2c_addresses||[]; i2c=[];
      machine.step(request.seconds,request.inputs||{});
      emit({ok:true,...machine.state(),serial,warnings,i2c}); serial=''; warnings=[];
    } else throw Error('Unknown command');
  } catch(error) {emit({ok:false,error:String(error.message)});}
});

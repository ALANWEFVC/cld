#!/usr/bin/env python3
# test_topology_fixed.py - 修复版Mininet测试拓扑

"""
创建一个用于测试IADS框架的Mininet拓扑（修复版）
修复的问题：
1. 修复OpenFlow13协议配置
2. 优化交换机配置
3. 改进链路参数设置
4. 增强错误处理

拓扑结构：
    h1 --- s1 --- s2 --- h2
            |      |
            +--s3--+
               |
               h3
"""

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time
import random
import threading
import sys


class OVSSwitch13(OVSSwitch):
    """OpenFlow 1.3 交换机"""
    def __init__(self, name, **params):
        params.setdefault('protocols', 'OpenFlow13')
        super(OVSSwitch13, self).__init__(name, **params)


class IADSTestTopologyFixed:
    """IADS测试拓扑（修复版）"""

    def __init__(self):
        self.net = None
        self.hosts = []
        self.switches = []
        self.links = []

    def create_topology(self):
        """创建测试拓扑"""
        info('*** Creating network\n')

        # 创建网络，使用自定义的OVSSwitch13
        self.net = Mininet(
            controller=RemoteController,
            switch=OVSSwitch13,  # 使用自定义的OpenFlow13交换机
            link=TCLink,
            autoSetMacs=True
        )

        info('*** Adding controller\n')
        c0 = self.net.addController(
            'c0',
            controller=RemoteController,
            ip='127.0.0.1',
            port=6633
        )

        info('*** Adding switches\n')
        # 添加交换机，使用简化配置
        s1 = self.net.addSwitch('s1', dpid='0000000000000001')
        s2 = self.net.addSwitch('s2', dpid='0000000000000002')
        s3 = self.net.addSwitch('s3', dpid='0000000000000003')
        self.switches = [s1, s2, s3]

        info('*** Adding hosts\n')
        # 添加主机
        h1 = self.net.addHost('h1', ip='10.0.0.1/24')
        h2 = self.net.addHost('h2', ip='10.0.0.2/24')
        h3 = self.net.addHost('h3', ip='10.0.0.3/24')
        self.hosts = [h1, h2, h3]

        info('*** Creating links\n')
        # 创建链路，使用简化参数
        self.net.addLink(h1, s1)
        self.net.addLink(s1, s2)
        self.net.addLink(s2, h2)
        self.net.addLink(s1, s3)
        self.net.addLink(s3, s2)
        self.net.addLink(s3, h3)

    def start(self):
        """启动网络"""
        info('*** Starting network\n')
        self.net.start()

        info('*** Configuring OpenFlow13\n')
        # 手动确保所有交换机使用OpenFlow13
        for switch in self.switches:
            info('Configuring {} for OpenFlow13\n'.format(switch.name))
            switch.cmd('ovs-vsctl set bridge %s protocols=OpenFlow13' % switch.name)

        info('*** Waiting for switches to connect to controller\n')
        time.sleep(8)

        # 检查控制器连接状态
        info('*** Checking controller connectivity\n')
        for switch in self.switches:
            info('Checking {}... '.format(switch.name))
            result = switch.cmd('ovs-vsctl show')
            if 'is_connected: true' in result:
                info('Connected\n')
            else:
                info('Not connected\n')

        # 检查OpenFlow版本
        info('*** Verifying OpenFlow13 configuration\n')
        for switch in self.switches:
            result = switch.cmd('ovs-vsctl get bridge %s protocols' % switch.name)
            info('{} protocols: {}\n'.format(switch.name, result.strip()))

        time.sleep(5)

        info('*** Testing basic connectivity\n')
        result = self.net.pingAll()
        if result == 0:
            info('*** All hosts can ping each other successfully!\n')
            return True
        else:
            info('*** Ping test failed with {}% packet loss\n'.format(result))
            
            # 调试信息
            info('*** Debugging information:\n')
            for switch in self.switches:
                info('=== {} Flow Tables ===\n'.format(switch.name))
                flows = switch.cmd('ovs-ofctl -O OpenFlow13 dump-flows %s' % switch.name)
                info('{}\n'.format(flows))
            
            return False
            
    def test_simple_connectivity(self):
        """测试基本连通性"""
        info('\n*** Testing simple connectivity\n')
        
        # 逐对测试ping
        for i, src in enumerate(self.hosts):
            for j, dst in enumerate(self.hosts):
                if i != j:
                    info('Testing {} -> {}: '.format(src.name, dst.name))
                    result = src.cmd('ping -c 1 -W 1 {}'.format(dst.IP()))
                    if '1 received' in result:
                        info('OK\n')
                    else:
                        info('FAILED\n')
                        info('  Debug info: {}\n'.format(result))

    def run_dynamic_scenarios(self):
        """运行动态场景以测试IADS的自适应能力"""
        info('\n*** Starting dynamic test scenarios\n')

        def scenario_thread():
            scenarios = [
                self._scenario_light_traffic,
                self._scenario_medium_traffic,
                self._scenario_connectivity_test,
            ]

            for i, scenario in enumerate(scenarios):
                time.sleep(20)
                info('\n*** Running scenario {}\n'.format(i+1))
                scenario()

        t = threading.Thread(target=scenario_thread)
        t.daemon = True
        t.start()

    def _scenario_light_traffic(self):
        """场景1：轻量流量测试"""
        info('\n*** Scenario 1: Light traffic test\n')
        h1, h2 = self.hosts[0], self.hosts[1]
        
        info('  - Light ping test from h1 to h2\n')
        result = h1.cmd('ping -c 5 10.0.0.2')
        if '5 received' in result:
            info('  - Light traffic test: PASSED\n')
        else:
            info('  - Light traffic test: FAILED\n')

    def _scenario_medium_traffic(self):
        """场景2：中等流量测试"""
        info('\n*** Scenario 2: Medium traffic test\n')
        h1, h2 = self.hosts[0], self.hosts[1]

        info('  - Starting medium traffic flow from h1 to h2\n')
        try:
            h2.cmd('iperf -s -p 5001 &')
            time.sleep(2)
            result = h1.cmd('iperf -c 10.0.0.2 -p 5001 -t 5 -b 10M')
            info('  - Traffic test result: {}\n'.format(result))
        except Exception as e:
            info('  - Traffic test failed: {}\n'.format(e))
        finally:
            h1.cmd('killall -9 iperf 2>/dev/null')
            h2.cmd('killall -9 iperf 2>/dev/null')

    def _scenario_connectivity_test(self):
        """场景3：连通性重测"""
        info('\n*** Scenario 3: Connectivity retest\n')
        
        result = self.net.pingAll()
        info('  - Connectivity retest result: {}% packet loss\n'.format(result))

    def cli(self):
        """启动CLI"""
        info('*** Running CLI\n')
        info('*** Available commands:\n')
        info('    pingall - Test connectivity between all hosts\n')
        info('    h1 ping h2 - Test connectivity between specific hosts\n')
        info('    nodes - Show all nodes\n')
        info('    links - Show all links\n')
        info('    dump - Show network configuration\n')
        info('    s1 ovs-ofctl -O OpenFlow13 dump-flows s1 - Show flow tables\n')
        CLI(self.net)

    def stop(self):
        """停止网络"""
        info('*** Stopping network\n')
        if self.net:
            self.net.stop()


def main():
    """主函数"""
    setLogLevel('info')

    topo = IADSTestTopologyFixed()

    try:
        topo.create_topology()
        success = topo.start()
        
        if success:
            info('\n*** Basic connectivity successful!\n')
            topo.run_dynamic_scenarios()
        else:
            info('\n*** Basic connectivity failed, entering CLI for debugging\n')
            topo.test_simple_connectivity()

        print("\n" + "="*50)
        print("IADS Test Topology is ready!")
        print("Basic connectivity test completed.")
        if success:
            print("All tests PASSED!")
        else:
            print("Some tests FAILED - check debugging info above")
        print("="*50 + "\n")
        
        topo.cli()

    except KeyboardInterrupt:
        info('\n*** Interrupted by user\n')
    except Exception as e:
        info('\n*** Error: {}\n'.format(e))
        import traceback
        traceback.print_exc()
    finally:
        topo.stop()


if __name__ == '__main__':
    main()

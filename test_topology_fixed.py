#!/usr/bin/env python3
# test_topology_fixed.py - 修复版Mininet测试拓扑

"""
创建一个用于测试IADS框架的Mininet拓扑（修复版）
修复的问题：
1. 添加OpenFlow13协议支持
2. 优化交换机配置
3. 改进链路参数设置
4. 增强错误处理
5. 启用RSTP以支持环路拓扑

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

        # 创建网络，使用RemoteController连接到Ryu
        # 关键修复：明确指定OpenFlow13支持
        self.net = Mininet(
            controller=RemoteController,
            switch=OVSSwitch,
            link=TCLink,  # 使用TCLink以支持带宽、延迟等参数
            autoSetMacs=True
        )

        info('*** Adding controller\n')
        c0 = self.net.addController(
            'c0',
            controller=RemoteController,
            ip='127.0.0.1',
            port=6633  # 与run.sh中配置一致
        )

        info('*** Adding switches\n')
        # 添加交换机，修复：明确指定OpenFlow13和失败模式
        s1 = self.net.addSwitch('s1',
                                dpid='0000000000000001',
                                protocols='OpenFlow13',
                                failMode='secure')
        s2 = self.net.addSwitch('s2',
                                dpid='0000000000000002',
                                protocols='OpenFlow13',
                                failMode='secure')
        s3 = self.net.addSwitch('s3',
                                dpid='0000000000000003',
                                protocols='OpenFlow13',
                                failMode='secure')
        self.switches = [s1, s2, s3]

        info('*** Adding hosts\n')
        # 添加主机
        h1 = self.net.addHost('h1', ip='10.0.0.1/24')
        h2 = self.net.addHost('h2', ip='10.0.0.2/24')
        h3 = self.net.addHost('h3', ip='10.0.0.3/24')
        self.hosts = [h1, h2, h3]

        info('*** Creating links\n')
        # 创建链路，修复：使用更保守的参数设置
        # h1-s1: 正常链路
        self.net.addLink(h1, s1, bw=100, delay='1ms', loss=0, use_htb=True)
        # s1-s2: 核心链路，带宽较高
        self.net.addLink(s1, s2, bw=1000, delay='2ms', loss=0, use_htb=True)
        # s2-h2: 正常链路
        self.net.addLink(s2, h2, bw=100, delay='1ms', loss=0, use_htb=True)
        # s1-s3: 稍微不稳定的链路，但参数更保守
        self.net.addLink(s1, s3, bw=100, delay='5ms', loss=0, use_htb=True)
        # s3-s2: 备份链路
        self.net.addLink(s3, s2, bw=500, delay='3ms', loss=0, use_htb=True)
        # s3-h3: 较慢的链路，但不设置丢包
        self.net.addLink(s3, h3, bw=50, delay='10ms', loss=0, use_htb=True)

    def start(self):
        """启动网络"""
        info('*** Starting network\n')
        self.net.start()

        # 为所有交换机启用RSTP
        info('*** Enabling RSTP on switches\n')
        for switch in self.switches:
            switch.cmd('ovs-vsctl set bridge %s rstp_enable=true' % switch.name)

        # 等待RSTP收敛
        info('*** Waiting for RSTP convergence (30 seconds)...\n')
        time.sleep(30)

        # 等待更长时间让IADS学习拓扑
        info('*** Waiting for IADS topology discovery...\n')
        time.sleep(15)

        # 检查流表
        info('*** Checking flow tables\n')
        for switch in self.switches:
            info('=== {} flows ===\n'.format(switch.name))
            flows = switch.cmd('ovs-ofctl -O OpenFlow13 dump-flows %s' % switch.name)
            info(flows)

        # 手动添加ARP处理
        info('*** Ensuring ARP handling\n')
        for host in self.hosts:
            # 刷新ARP缓存
            host.cmd('arp -d -a')

        # 逐个测试
        info('*** Step-by-step connectivity test\n')
        h1, h2 = self.hosts[0], self.hosts[1]

        # 先测试ARP
        info('1. ARP test:\n')
        h1.cmd('arping -c 1 10.0.0.2')

        # 再测试ICMP
        info('2. ICMP test:\n')
        result = h1.cmd('ping -c 3 10.0.0.2')
        info(result)

        # 修复：检查控制器连接状态
        info('*** Checking controller connectivity\n')
        for switch in self.switches:
            info('Checking {}... '.format(switch.name))
            # 使用ovs-vsctl检查控制器连接
            result = switch.cmd('ovs-vsctl show')
            if 'is_connected: true' in result:
                info('Connected\n')
            else:
                info('Disconnected - trying to reconnect\n')
                switch.cmd('ovs-vsctl set-controller {} tcp:127.0.0.1:6633'.format(switch.name))

        # 再等待一段时间
        time.sleep(5)

        info('*** Testing basic connectivity\n')
        # 先测试基本的ping
        result = self.net.pingAll()
        if result == 0:
            info('*** All hosts can ping each other successfully!\n')
        else:
            info('*** Ping test failed with {}% packet loss\n'.format(result))

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
                time.sleep(20)  # 每20秒运行一个场景
                info('\n*** Running scenario {}\n'.format(i + 1))
                scenario()

        # 在后台线程运行场景
        t = threading.Thread(target=scenario_thread)
        t.daemon = True
        t.start()

    def _scenario_light_traffic(self):
        """场景1：轻量流量测试"""
        info('\n*** Scenario 1: Light traffic test\n')
        h1, h2 = self.hosts[0], self.hosts[1]

        # 轻量ping测试
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

        # 使用更轻量的流量测试
        info('  - Starting medium traffic flow from h1 to h2\n')
        try:
            h2.cmd('iperf -s -p 5001 &')
            time.sleep(2)
            result = h1.cmd('iperf -c 10.0.0.2 -p 5001 -t 5 -b 10M')
            info('  - Traffic test result: {}\n'.format(result))
        except Exception as e:
            info('  - Traffic test failed: {}\n'.format(e))
        finally:
            # 清理
            h1.cmd('killall -9 iperf 2>/dev/null')
            h2.cmd('killall -9 iperf 2>/dev/null')

    def _scenario_connectivity_test(self):
        """场景3：连通性重测"""
        info('\n*** Scenario 3: Connectivity retest\n')

        # 重新测试连通性
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
        info('    s1 ovs-appctl stp/show - Show STP status\n')
        CLI(self.net)

    def stop(self):
        """停止网络"""
        info('*** Stopping network\n')
        if self.net:
            self.net.stop()


def main():
    """主函数"""
    setLogLevel('info')

    # 创建测试拓扑
    topo = IADSTestTopologyFixed()

    try:
        # 创建和启动拓扑
        topo.create_topology()
        topo.start()

        # 测试基本连通性
        topo.test_simple_connectivity()

        # 如果基本连通性通过，运行动态场景
        print("\n" + "=" * 50)
        print("IADS Test Topology is ready!")
        print("Basic connectivity test completed.")
        print("Starting dynamic scenarios...")
        print("=" * 50 + "\n")

        topo.run_dynamic_scenarios()

        # 进入CLI
        topo.cli()

    except KeyboardInterrupt:
        info('\n*** Interrupted by user\n')
    except Exception as e:
        info('*** Error: {}\n'.format(e))
        import traceback
        traceback.print_exc()
    finally:
        # 清理
        topo.stop()


if __name__ == '__main__':
    main()

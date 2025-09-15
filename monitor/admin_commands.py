"""
Admin commands for monitoring and diagnostics
"""
from typing import Dict, Any, Optional
from datetime import datetime
import json
from telegram import Update
from telegram.ext import CallbackContext
from monitor.observability import ObservabilityManager
from monitor.health_checks import HealthChecker

class AdminCommands:
    """Admin command handlers for monitoring and diagnostics"""
    
    def __init__(
        self,
        observability: ObservabilityManager,
        health_checker: HealthChecker
    ):
        self.observability = observability
        self.health_checker = health_checker
        
    async def handle_diagnostics(
        self,
        update: Update,
        context: CallbackContext
    ):
        """Handle /admin diagnostics command"""
        try:
            # Get health status
            health = await self.health_checker.check_all()
            system_ok = all(
                s['status'] == 'healthy'
                for s in health['system'].values()
            )
            
            apis_ok = all(
                api['status_code'] == 200
                for api in health['apis'].values()
            )
            
            infra_ok = all(
                component['status'] == 'healthy'
                for component in health['infrastructure'].values()
            )
            
            # Format message
            lines = [
                "📊 System Diagnostics",
                "==================="
            ]
            
            # System status
            lines.extend([
                "",
                "💻 System Status:",
                f"{'✅' if system_ok else '⚠️'} CPU: {health['system']['cpu_percent']}%",
                f"{'✅' if system_ok else '⚠️'} Memory: {health['system']['memory_usage']['percent']}%",
                f"{'✅' if system_ok else '⚠️'} Disk: {health['system']['disk_usage']['percent']}%"
            ])
            
            # API status
            lines.extend([
                "",
                "🌐 API Status:"
            ])
            
            for api_name, api_status in health['apis'].items():
                status_icon = '✅' if api_status['status_code'] == 200 else '⚠️'
                lines.append(
                    f"{status_icon} {api_name}: "
                    f"{api_status['status_code']} "
                    f"({api_status['response_time']:.2f}s)"
                )
                
            # Infrastructure status
            lines.extend([
                "",
                "🔧 Infrastructure:"
            ])
            
            redis_status = health['infrastructure']['redis']
            cache_status = health['infrastructure']['cache']
            
            lines.extend([
                f"{'✅' if redis_status['status'] == 'healthy' else '⚠️'} Redis: {redis_status['status']}",
                f"{'✅' if cache_status['status'] == 'healthy' else '⚠️'} Cache: {cache_status['status']}"
            ])
            
            # Performance metrics
            lines.extend([
                "",
                "📈 Performance Metrics:"
            ])
            
            for module_name in self.observability.module_metrics:
                metrics = self.observability.get_module_metrics(module_name)
                lines.extend([
                    f"📊 {module_name}:",
                    f"- Success Rate: {metrics['success_rate']:.1%}",
                    f"- Avg Time: {metrics['avg_operation_time']:.2f}s",
                    f"- Errors: {metrics['error_count']}"
                ])
                
                if metrics['last_error']:
                    lines.append(
                        f"- Last Error: {metrics['last_error']} "
                        f"at {metrics['last_error_time']}"
                    )
                    
            # Network latency
            lines.extend([
                "",
                "🌍 Network Latency:"
            ])
            
            for chain, latency in health['network'].items():
                if 'error' in latency:
                    lines.append(f"❌ {chain}: Error - {latency['error']}")
                else:
                    lines.append(
                        f"✅ {chain}: {latency['latency']:.2f}s"
                    )
                    
            # Recovery suggestions
            if not all([system_ok, apis_ok, infra_ok]):
                lines.extend([
                    "",
                    "🔨 Recovery Suggestions:"
                ])
                
                if not system_ok:
                    lines.append(
                        "- System resources are high, consider scaling up or optimizing"
                    )
                    
                if not apis_ok:
                    lines.append(
                        "- Some APIs are failing, check rate limits and API keys"
                    )
                    
                if not infra_ok:
                    lines.append(
                        "- Infrastructure issues detected, verify Redis and cache connectivity"
                    )
                    
            # Send message
            await update.message.reply_text(
                "\n".join(lines)
            )
            
        except Exception as e:
            error_msg = (
                "❌ Error running diagnostics:\n"
                f"{str(e)}\n\n"
                "Please check logs for details."
            )
            await update.message.reply_text(error_msg)
            
    async def handle_performance(
        self,
        update: Update,
        context: CallbackContext
    ):
        """Handle /admin performance command"""
        try:
            lines = [
                "📊 Performance Analysis",
                "===================="
            ]
            
            # Module performance
            for module_name in self.observability.module_metrics:
                metrics = self.observability.get_module_metrics(
                    module_name
                )
                
                lines.extend([
                    f"\n📈 {module_name}:",
                    f"Uptime: {metrics['uptime'] / 3600:.1f} hours",
                    f"Success Rate: {metrics['success_rate']:.1%}",
                    f"Average Operation Time: {metrics['avg_operation_time']:.2f}s",
                    f"Error Count: {metrics['error_count']}"
                ])
                
                if metrics['last_error']:
                    lines.extend([
                        "Last Error:",
                        f"- Message: {metrics['last_error']}",
                        f"- Time: {metrics['last_error_time']}"
                    ])
                    
            # System metrics
            system = self.observability.get_system_metrics()
            lines.extend([
                "\n💻 System Metrics:",
                f"CPU Usage: {system['cpu_percent']}%",
                f"Memory Usage: {system['memory_percent']}%",
                f"Disk Usage: {system['disk_usage']}%",
                f"Open Files: {system['open_files']}",
                f"Active Connections: {system['connections']}"
            ])
            
            await update.message.reply_text(
                "\n".join(lines)
            )
            
        except Exception as e:
            error_msg = (
                "❌ Error getting performance metrics:\n"
                f"{str(e)}\n\n"
                "Please check logs for details."
            )
            await update.message.reply_text(error_msg)
            
    async def handle_errors(
        self,
        update: Update,
        context: CallbackContext
    ):
        """Handle /admin errors command"""
        try:
            lines = [
                "❌ Error Summary",
                "=============="
            ]
            
            has_errors = False
            for module_name in self.observability.module_metrics:
                metrics = self.observability.get_module_metrics(
                    module_name
                )
                
                if metrics['error_count'] > 0:
                    has_errors = True
                    lines.extend([
                        f"\n🔍 {module_name}:",
                        f"Total Errors: {metrics['error_count']}",
                        "Last Error:",
                        f"- Message: {metrics['last_error']}",
                        f"- Time: {metrics['last_error_time']}"
                    ])
                    
            if not has_errors:
                lines.append("\n✅ No errors reported!")
                
            await update.message.reply_text(
                "\n".join(lines)
            )
            
        except Exception as e:
            error_msg = (
                "❌ Error getting error summary:\n"
                f"{str(e)}\n\n"
                "Please check logs for details."
            )
            await update.message.reply_text(error_msg)

using System;
using System.Runtime.InteropServices;
using Godot;

namespace Volibear;

/// <summary>Read-only OS observations for the controlled presentation probe; never sends input or activates a window.</summary>
internal static class NativeWindowProbe
{
    [StructLayout(LayoutKind.Sequential)]
    private struct Rect { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll", EntryPoint = "GetWindowLongW")]
    private static extern int GetWindowLong(nint window, int index);
    [DllImport("user32.dll")]
    private static extern bool GetClientRect(nint window, out Rect rect);
    [DllImport("user32.dll")]
    private static extern bool GetWindowRect(nint window, out Rect rect);
    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint process);
    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(nint window);
    [DllImport("user32.dll")]
    private static extern bool IsWindowEnabled(nint window);
    [DllImport("user32.dll")]
    private static extern bool IsIconic(nint window);
    [DllImport("user32.dll")]
    private static extern bool IsZoomed(nint window);

    internal static object Capture()
    {
        if (!OperatingSystem.IsWindows())
            return new { platform = OS.GetName(), status = "not-applicable" };

        var window = (nint)DisplayServer.WindowGetNativeHandle(DisplayServer.HandleType.WindowHandle);
        var style = unchecked((uint)GetWindowLong(window, -16));
        var extended = unchecked((uint)GetWindowLong(window, -20));
        var thread = GetWindowThreadProcessId(window, out var process);
        bool clientOk = GetClientRect(window, out var client);
        bool outerOk = GetWindowRect(window, out var outer);
        bool visible = IsWindowVisible(window), enabled = IsWindowEnabled(window);
        bool minimized = IsIconic(window), maximized = IsZoomed(window);
        var result = new { platform = "Windows", hwnd = window.ToInt64(), process, thread,
            style, extendedStyle = extended, visible, enabled, minimized, maximized,
            clientWidth = client.Right - client.Left, clientHeight = client.Bottom - client.Top,
            outerWidth = outer.Right - outer.Left, outerHeight = outer.Bottom - outer.Top };
        GD.Print("[Volibear] NATIVE_WINDOW " + System.Text.Json.JsonSerializer.Serialize(result));
        const uint required = 0x00C00000 | 0x00080000; // caption and system menu (resizing is optional)
        const uint forbidden = 0x08000000 | 0x40000000 | 0x80000000; // disabled, child, popup
        const uint forbiddenExtended = 0x80 | 0x8 | 0x08000000 | 0x20; // tool, topmost, no-activate, transparent
        if (window == 0 || thread == 0 || process != Environment.ProcessId || !clientOk || !outerOk ||
            (style & required) != required || (style & forbidden) != 0 || (extended & forbiddenExtended) != 0 ||
            !visible || !enabled || minimized || maximized ||
            result.clientWidth != 1280 || result.clientHeight != 720 ||
            result.outerWidth <= result.clientWidth || result.outerHeight <= result.clientHeight)
            throw new InvalidOperationException("Native Windows presentation window must be a normal enabled, decorated 1280x720 window; see NATIVE_WINDOW observations.");
        return result;
    }
}

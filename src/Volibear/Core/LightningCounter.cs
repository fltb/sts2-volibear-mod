using System;
using System.Collections.Generic;

namespace Volibear.Core;

/// <summary>
/// Bookkeeping only: no damage/HP simulation. One instance belongs to one creature in
/// one combat. Player turn number distinguishes extra turns inside the same round.
/// Pending work from another turn, a reset or an exception can never complete twice.
/// </summary>
public sealed class LightningCounter
{
    private readonly HashSet<long> _pending = [];
    private long _nextId;
    private int _generation;
    private int _round = -1;
    private int _turn = -1;
    private int _completed;
    public bool IsClosed { get; private set; }

    public readonly record struct Ticket(long Id, int Generation, int Round, int PlayerTurn);

    public int Read(int round, int playerTurn)
    {
        if (IsClosed) return 0;
        SetEpoch(round, playerTurn);
        return _completed;
    }

    public Ticket Begin(int round, int playerTurn)
    {
        if (IsClosed) throw new InvalidOperationException("Lightning combat scope is closed.");
        SetEpoch(round, playerTurn);
        var ticket = new Ticket(checked(++_nextId), _generation, round, playerTurn);
        _pending.Add(ticket.Id);
        return ticket;
    }

    public bool Complete(Ticket ticket, out int countThisTurn)
    {
        countThisTurn = _completed;
        if (IsClosed || ticket.Generation != _generation || ticket.Round != _round ||
            ticket.PlayerTurn != _turn || !_pending.Remove(ticket.Id)) return false;
        countThisTurn = checked(++_completed);
        return true;
    }

    public void Abort(Ticket ticket)
    {
        if (ticket.Generation == _generation) _pending.Remove(ticket.Id);
    }

    public void Close()
    {
        IsClosed = true;
        _pending.Clear();
        _completed = 0;
        _generation++;
    }

    private void SetEpoch(int round, int playerTurn)
    {
        if (round < 0 || playerTurn < 0) throw new ArgumentOutOfRangeException(nameof(round));
        if (_round == round && _turn == playerTurn) return;
        _round = round;
        _turn = playerTurn;
        _completed = 0;
        _pending.Clear();
        _generation++;
    }
}

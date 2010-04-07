package autotest.common.spreadsheet;

import autotest.common.Utils;
import autotest.common.spreadsheet.Spreadsheet.CellInfo;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;

// TODO: hopefully some of this could be combined with autotest.common.table.SelectionManager using
// generics
// TODO: get rid of header selection
public class SpreadsheetSelectionManager {
    private Spreadsheet spreadsheet;
    private Collection<CellInfo> selectedCells = new HashSet<CellInfo>();
    private SpreadsheetSelectionListener listener;
    
    public static interface SpreadsheetSelectionListener {
        public void onCellsSelected(List<CellInfo> cells);
        public void onCellsDeselected(List<CellInfo> cells);
    }
    
    public SpreadsheetSelectionManager(Spreadsheet spreadsheet, 
                                       SpreadsheetSelectionListener listener) {
        this.spreadsheet = spreadsheet;
        this.listener = listener;
    }
    
    public void toggleSelected(CellInfo cell) {
        if (selectedCells.contains(cell)) {
            deselectCell(cell);
            notifyDeselected(Utils.wrapObjectWithList(cell));
        } else {
            selectCell(cell);
            notifySelected(Utils.wrapObjectWithList(cell));
        }
    }

    private void selectCell(CellInfo cell) {
        selectedCells.add(cell);
        spreadsheet.setHighlighted(cell, true);
    }

    private void deselectCell(CellInfo cell) {
        selectedCells.remove(cell);
        spreadsheet.setHighlighted(cell, false);
    }
    
    public List<CellInfo> getSelectedCells() {
        return new ArrayList<CellInfo>(selectedCells);
    }
    
    public boolean isEmpty() {
        return selectedCells.isEmpty();
    }
    
    public void clearSelection() {
        List<CellInfo> cells = getSelectedCells();
        for (CellInfo cell : cells) {
            deselectCell(cell);
        }
        notifyDeselected(cells);
    }

    public void selectAll() {
        List<CellInfo> selectedCells = new ArrayList<CellInfo>();
        for (CellInfo[] row : spreadsheet.dataCells) {
            for (CellInfo cell : row) {
                if (cell == null || cell.isEmpty()) {
                    continue;
                }
                selectCell(cell);
                selectedCells.add(cell);
            }
        }
        notifySelected(selectedCells);
    }
    
    private void notifyDeselected(List<CellInfo> cells) {
        if (listener != null) {
            listener.onCellsDeselected(cells);
        }
    }

    private void notifySelected(List<CellInfo> selectedCells) {
        if (listener != null) {
            listener.onCellsSelected(selectedCells);
        }
    }
}

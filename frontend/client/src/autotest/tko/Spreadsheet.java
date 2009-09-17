package autotest.tko;

import autotest.common.UnmodifiableSublistView;
import autotest.common.Utils;
import autotest.common.ui.RightClickTable;

import com.google.gwt.dom.client.Element;
import com.google.gwt.event.dom.client.ScrollEvent;
import com.google.gwt.event.dom.client.ScrollHandler;
import com.google.gwt.user.client.DeferredCommand;
import com.google.gwt.user.client.IncrementalCommand;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HTMLTable;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.ScrollPanel;
import com.google.gwt.user.client.ui.SimplePanel;
import com.google.gwt.user.client.ui.SourcesTableEvents;
import com.google.gwt.user.client.ui.TableListener;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class Spreadsheet extends Composite implements ScrollHandler, TableListener {
    private static final int MIN_TABLE_SIZE_PX = 90;
    private static final int WINDOW_BORDER_PX = 15;
    private static final int SCROLLBAR_FUDGE = 16;
    private static final String BLANK_STRING = "(empty)";
    private static final int CELL_PADDING_PX = 2;
    private static final int TD_BORDER_PX = 1;
    private static final String HIGHLIGHTED_CLASS = "highlighted";
    private static final int CELLS_PER_ITERATION = 1000;
    
    private Header rowFields, columnFields;
    private List<Header> rowHeaderValues = new ArrayList<Header>();
    private List<Header> columnHeaderValues = new ArrayList<Header>();
    private Map<Header, Integer> rowHeaderMap = new HashMap<Header, Integer>();
    private Map<Header, Integer> columnHeaderMap = new HashMap<Header, Integer>();
    protected CellInfo[][] dataCells, rowHeaderCells, columnHeaderCells;
    private RightClickTable rowHeaders = new RightClickTable();
    private RightClickTable columnHeaders = new RightClickTable();
    private FlexTable parentTable = new FlexTable();
    private FragmentedTable dataTable = new FragmentedTable();
    private int rowsPerIteration;
    private Panel rowHeadersClipPanel, columnHeadersClipPanel;
    private ScrollPanel scrollPanel = new ScrollPanel(dataTable);
    private TableRenderer renderer = new TableRenderer();
    
    private SpreadsheetListener listener;
    
    public interface SpreadsheetListener {
        public void onCellClicked(CellInfo cellInfo);
    }
    
    public static interface Header extends List<String> {}
    public static class HeaderImpl extends ArrayList<String> implements Header {
        public HeaderImpl() {
        }

        public HeaderImpl(Collection<? extends String> arg0) {
            super(arg0);
        }

        public static Header fromBaseType(List<String> baseType) {
            return new HeaderImpl(baseType);
        }
    }
    
    public static class CellInfo {
        public Header row, column;
        public String contents;
        public String color;
        public Integer widthPx, heightPx;
        public int rowSpan = 1, colSpan = 1;
        public int testCount = 0;
        public int testIndex;
        
        public CellInfo(Header row, Header column, String contents) {
            this.row = row;
            this.column = column;
            this.contents = contents;
        }
        
        public boolean isHeader() {
            return !isEmpty() && (row == null || column == null);
        }
        
        public boolean isEmpty() {
            return row == null && column == null;
        }
    }
    
    private class RenderCommand implements IncrementalCommand {
        private int state = 0;
        private int rowIndex = 0;
        private IncrementalCommand onFinished;
        
        public RenderCommand(IncrementalCommand onFinished) {
            this.onFinished = onFinished;
        }
        
        private void renderSomeRows() {
            renderer.renderRowsAndAppend(dataTable, dataCells, 
                                         rowIndex, rowsPerIteration, true);
            rowIndex += rowsPerIteration;
            if (rowIndex > dataCells.length) {
                state++;
            }
        }
        
        public boolean execute() {
            switch (state) {
                case 0:
                    computeRowsPerIteration();
                    computeHeaderCells();
                    break;
                case 1:
                    renderHeaders();
                    expandRowHeaders();
                    break;
                case 2:
                    // resize everything to the max dimensions (the window size)
                    fillWindow(false);
                    break;
                case 3:
                    // set main table to match header sizes
                    matchRowHeights(rowHeaders, dataCells);
                    matchColumnWidths(columnHeaders, dataCells);
                    dataTable.setVisible(false);
                    break;
                case 4:
                    // render the main data table
                    renderSomeRows();
                    return true;
                case 5:
                    dataTable.updateBodyElems();
                    dataTable.setVisible(true);
                    break;
                case 6:
                    // now expand headers as necessary
                    // this can be very slow, so put it in it's own cycle
                    matchRowHeights(dataTable, rowHeaderCells);
                    break;
                case 7:
                    matchColumnWidths(dataTable, columnHeaderCells);
                    renderHeaders();
                    break;
                case 8:
                    // shrink the scroller if the table ended up smaller than the window
                    fillWindow(true);
                    DeferredCommand.addCommand(onFinished);
                    return false;
            }
            
            state++;
            return true;
        }
    }

    public Spreadsheet() {
        dataTable.setStyleName("spreadsheet-data");
        killPaddingAndSpacing(dataTable);
        
        rowHeaders.setStyleName("spreadsheet-headers");
        killPaddingAndSpacing(rowHeaders);
        rowHeadersClipPanel = wrapWithClipper(rowHeaders);
        
        columnHeaders.setStyleName("spreadsheet-headers");
        killPaddingAndSpacing(columnHeaders);
        columnHeadersClipPanel = wrapWithClipper(columnHeaders);
        
        scrollPanel.setStyleName("spreadsheet-scroller");
        scrollPanel.setAlwaysShowScrollBars(true);
        scrollPanel.addScrollHandler(this);
        
        parentTable.setStyleName("spreadsheet-parent");
        killPaddingAndSpacing(parentTable);
        parentTable.setWidget(0, 1, columnHeadersClipPanel);
        parentTable.setWidget(1, 0, rowHeadersClipPanel);
        parentTable.setWidget(1, 1, scrollPanel);
        
        setupTableInput(dataTable);
        setupTableInput(rowHeaders);
        setupTableInput(columnHeaders);
        
        initWidget(parentTable);
    }

    private void setupTableInput(RightClickTable table) {
        table.sinkRightClickEvents();
        table.addTableListener(this);
    }

    protected void killPaddingAndSpacing(HTMLTable table) {
        table.setCellSpacing(0);
        table.setCellPadding(0);
    }
    
    /*
     * Wrap a widget with a panel that will clip its contents rather than grow
     * too much.
     */
    protected Panel wrapWithClipper(Widget w) {
        SimplePanel wrapper = new SimplePanel();
        wrapper.add(w);
        wrapper.setStyleName("clipper");
        return wrapper;
    }
    
    public void setHeaderFields(Header rowFields, Header columnFields) {
        this.rowFields = rowFields;
        this.columnFields = columnFields;
    }
    
    private void addHeader(List<Header> headerList, Map<Header, Integer> headerMap,
                          List<String> header) {
        Header headerObject = HeaderImpl.fromBaseType(header);
        assert !headerMap.containsKey(headerObject);
        headerList.add(headerObject);
        headerMap.put(headerObject, headerMap.size());
    }
    
    public void addRowHeader(List<String> header) {
        addHeader(rowHeaderValues, rowHeaderMap, header);
    }
    
    public void addColumnHeader(List<String> header) {
        addHeader(columnHeaderValues, columnHeaderMap, header);
    }
    
    private int getHeaderPosition(Map<Header, Integer> headerMap, Header header) {
        assert headerMap.containsKey(header);
        return headerMap.get(header);
    }
    
    private int getRowPosition(Header rowHeader) {
        return getHeaderPosition(rowHeaderMap, rowHeader);
    }
    
    private int getColumnPosition(Header columnHeader) {
        return getHeaderPosition(columnHeaderMap, columnHeader);
    }
    
    /**
     * Must be called after adding headers but before adding data
     */
    public void prepareForData() {
        dataCells = new CellInfo[rowHeaderValues.size()][columnHeaderValues.size()];
    }

    public CellInfo getCellInfo(int row, int column) {
        Header rowHeader = rowHeaderValues.get(row);
        Header columnHeader = columnHeaderValues.get(column);
        if (dataCells[row][column] == null) {
            dataCells[row][column] = new CellInfo(rowHeader, columnHeader, "");
        }
        return dataCells[row][column];
    }
    
    private CellInfo getCellInfo(CellInfo[][] cells, int row, int column) {
        if (cells[row][column] == null) {
            cells[row][column] = new CellInfo(null, null, " ");
        }
        return cells[row][column];
    }
    
    /**
     * Render the data into HTML tables.  Done through a deferred command.
     */
    public void render(IncrementalCommand onFinished) {
        DeferredCommand.addCommand(new RenderCommand(onFinished));
    }

    private void renderHeaders() {
        renderer.renderRows(rowHeaders, rowHeaderCells, false);
        renderer.renderRows(columnHeaders, columnHeaderCells, false);
    }
    
    public void computeRowsPerIteration() {
        int cellsPerRow = columnHeaderValues.size();
        rowsPerIteration = Math.max(CELLS_PER_ITERATION / cellsPerRow, 1);
        dataTable.setRowsPerFragment(rowsPerIteration);
    }
    
    private void computeHeaderCells() {
        rowHeaderCells = new CellInfo[rowHeaderValues.size()][rowFields.size()];
        fillHeaderCells(rowHeaderCells, rowFields, rowHeaderValues, true);
        
        columnHeaderCells = new CellInfo[columnFields.size()][columnHeaderValues.size()];
        fillHeaderCells(columnHeaderCells, columnFields, columnHeaderValues, false);
    }
    
    /**
     * TODO (post-1.0) - this method needs good cleanup and documentation
     */
    private void fillHeaderCells(CellInfo[][] cells, Header fields, List<Header> headerValues, 
                                 boolean isRows) {
        int headerSize = fields.size();
        String[] lastFieldValue = new String[headerSize];
        CellInfo[] lastCellInfo = new CellInfo[headerSize];
        int[] counter = new int[headerSize];
        boolean newHeader;
        for (int headerIndex = 0; headerIndex < headerValues.size(); headerIndex++) {
            Header header = headerValues.get(headerIndex);
            newHeader = false;
            for (int fieldIndex = 0; fieldIndex < headerSize; fieldIndex++) {
                String fieldValue = header.get(fieldIndex);
                if (newHeader || !fieldValue.equals(lastFieldValue[fieldIndex])) {
                    newHeader = true;
                    Header currentHeader = getSubHeader(header, fieldIndex + 1);
                    String cellContents = formatHeader(fields.get(fieldIndex), fieldValue);
                    CellInfo cellInfo;
                    if (isRows) {
                        cellInfo = new CellInfo(currentHeader, null, cellContents);
                        cells[headerIndex][fieldIndex] = cellInfo;
                    } else {
                        cellInfo = new CellInfo(null, currentHeader, cellContents);
                        cells[fieldIndex][counter[fieldIndex]] = cellInfo;
                        counter[fieldIndex]++;
                    }
                    lastFieldValue[fieldIndex] = fieldValue;
                    lastCellInfo[fieldIndex] = cellInfo;
                } else {
                    incrementSpan(lastCellInfo[fieldIndex], isRows);
                }
            }
        }
    }
    
    private String formatHeader(String field, String value) {
        if (value.equals("")) {
            return BLANK_STRING;
        }
        value = Utils.escape(value);
        if (field.equals("kernel")) {
            // line break after each /, for long paths
            value = value.replace("/", "/<br>").replace("/<br>/<br>", "//");
        }
        return value;
    }

    private void incrementSpan(CellInfo cellInfo, boolean isRows) {
        if (isRows) {
            cellInfo.rowSpan++;
        } else {
            cellInfo.colSpan++;
        }
    }

    private Header getSubHeader(Header header, int length) {
        if (length == header.size()) {
            return header;
        }
        List<String> subHeader = new UnmodifiableSublistView<String>(header, 0, length);
        return new HeaderImpl(subHeader);
    }

    private void matchRowHeights(HTMLTable from, CellInfo[][] to) {
        int lastColumn = to[0].length - 1;
        int rowCount = from.getRowCount();
        for (int row = 0; row < rowCount; row++) {
            int height = getRowHeight(from, row);
            getCellInfo(to, row, lastColumn).heightPx = height - 2 * CELL_PADDING_PX;
        }
    }
    
    private void matchColumnWidths(HTMLTable from, CellInfo[][] to) {
        int lastToRow = to.length - 1;
        int lastFromRow = from.getRowCount() - 1;
        for (int column = 0; column < from.getCellCount(lastFromRow); column++) {
            int width = getColumnWidth(from, column);
            getCellInfo(to, lastToRow, column).widthPx = width - 2 * CELL_PADDING_PX;
        }
    }
    
    protected String getTableCellText(HTMLTable table, int row, int column) {
        Element td = table.getCellFormatter().getElement(row, column);
        Element div = td.getFirstChildElement();
        if (div == null)
            return null;
        String contents = Utils.unescape(div.getInnerHTML());
        if (contents.equals(BLANK_STRING))
            contents = "";
        return contents;
    }

    public void clear() {
        rowHeaderValues.clear();
        columnHeaderValues.clear();
        rowHeaderMap.clear();
        columnHeaderMap.clear();
        dataCells = rowHeaderCells = columnHeaderCells = null;
        dataTable.reset();
        
        setRowHeadersOffset(0);
        setColumnHeadersOffset(0);
    }
    
    /**
     * Make the spreadsheet fill the available window space to the right and bottom
     * of its position.
     */
    public void fillWindow(boolean useTableSize) {
        int newHeightPx = Window.getClientHeight() - (columnHeaders.getAbsoluteTop() + 
                                                      columnHeaders.getOffsetHeight());
        newHeightPx = adjustMaxDimension(newHeightPx);
        int newWidthPx = Window.getClientWidth() - (rowHeaders.getAbsoluteLeft() + 
                                                    rowHeaders.getOffsetWidth());
        newWidthPx = adjustMaxDimension(newWidthPx);
        if (useTableSize) {
            newHeightPx = Math.min(newHeightPx, rowHeaders.getOffsetHeight());
            newWidthPx = Math.min(newWidthPx, columnHeaders.getOffsetWidth());
        }
        
        // apply the changes all together
        rowHeadersClipPanel.setHeight(getSizePxString(newHeightPx));
        columnHeadersClipPanel.setWidth(getSizePxString(newWidthPx));
        scrollPanel.setSize(getSizePxString(newWidthPx + SCROLLBAR_FUDGE),
                            getSizePxString(newHeightPx + SCROLLBAR_FUDGE));
    }

    /**
     * Adjust a maximum table dimension to allow room for edge decoration and 
     * always maintain a minimum height
     */
    protected int adjustMaxDimension(int maxDimensionPx) {
        return Math.max(maxDimensionPx - WINDOW_BORDER_PX - SCROLLBAR_FUDGE, 
                        MIN_TABLE_SIZE_PX);
    }

    protected String getSizePxString(int sizePx) {
        return sizePx + "px";
    }
    
    /**
     * Ensure the row header clip panel allows the full width of the row headers
     * to display.
     */
    protected void expandRowHeaders() {
        int width = rowHeaders.getOffsetWidth();
        rowHeadersClipPanel.setWidth(getSizePxString(width));
    }
    
    private Element getCellElement(HTMLTable table, int row, int column) {
        return table.getCellFormatter().getElement(row, column);
    }
    
    private Element getCellElement(CellInfo cellInfo) {
        assert cellInfo.row != null || cellInfo.column != null;
        Element tdElement;
        if (cellInfo.row == null) {
            tdElement = getCellElement(columnHeaders, 0, getColumnPosition(cellInfo.column));
        } else if (cellInfo.column == null) {
            tdElement = getCellElement(rowHeaders, getRowPosition(cellInfo.row), 0);
        } else {
            tdElement = getCellElement(dataTable, getRowPosition(cellInfo.row), 
                                                  getColumnPosition(cellInfo.column));
        }
        Element cellElement = tdElement.getFirstChildElement();
        assert cellElement != null;
        return cellElement;
    }
    
    protected int getColumnWidth(HTMLTable table, int column) {
        // using the column formatter doesn't seem to work
        int numRows = table.getRowCount();
        return table.getCellFormatter().getElement(numRows - 1, column).getOffsetWidth() - 
               TD_BORDER_PX;
    }
    
    protected int getRowHeight(HTMLTable table, int row) {
        // see getColumnWidth()
        int numCols = table.getCellCount(row);
        return table.getCellFormatter().getElement(row, numCols - 1).getOffsetHeight() - 
               TD_BORDER_PX;
    }

    /**
     * Update floating headers.
     */
    @Override
    public void onScroll(ScrollEvent event) {
        int scrollLeft = scrollPanel.getHorizontalScrollPosition();
        int scrollTop = scrollPanel.getScrollPosition();
        
        setColumnHeadersOffset(-scrollLeft);
        setRowHeadersOffset(-scrollTop);
    }

    protected void setRowHeadersOffset(int offset) {
        rowHeaders.getElement().getStyle().setPropertyPx("top", offset);
    }

    protected void setColumnHeadersOffset(int offset) {
        columnHeaders.getElement().getStyle().setPropertyPx("left", offset);
    }

    public void onCellClicked(SourcesTableEvents sender, int row, int column) {
        if (listener == null)
            return;
        
        CellInfo[][] cells;
        if (sender == rowHeaders) {
            cells = rowHeaderCells;
            column = adjustRowHeaderColumnIndex(row, column);
        }
        else if (sender == columnHeaders) {
            cells = columnHeaderCells;
        }
        else {
            assert sender == dataTable;
            cells = dataCells;
        }
        CellInfo cell = cells[row][column];
        if (cell == null || cell.isEmpty())
            return; // don't report clicks on empty cells
        listener.onCellClicked(cell);
    }

    /**
     * In HTMLTables, a cell with rowspan > 1 won't count in column indices for the extra rows it 
     * spans, which will mess up column indices for other cells in those rows.  This method adjusts
     * the column index passed to onCellClicked() to account for that.
     */
    private int adjustRowHeaderColumnIndex(int row, int column) {
        for (int i = 0; i < rowFields.size(); i++) {
            if (rowHeaderCells[row][i] != null) {
                return i + column;
            }
        }
        
        throw new RuntimeException("Failed to find non-null cell");
    }

    public void setListener(SpreadsheetListener listener) {
        this.listener = listener;
    }

    public void setHighlighted(CellInfo cell, boolean highlighted) {
        Element cellElement = getCellElement(cell);
        if (highlighted) {
            cellElement.setClassName(HIGHLIGHTED_CLASS);
        } else {
            cellElement.setClassName("");
        }
    }
    
    public List<Integer> getAllTestIndices() {
        List<Integer> testIndices = new ArrayList<Integer>();

        for (CellInfo[] row : dataCells) {
            for (CellInfo cellInfo : row) {
                if (cellInfo != null && !cellInfo.isEmpty()) {
                    testIndices.add(cellInfo.testIndex);
                }
            }
        }

        return testIndices;
    }
}

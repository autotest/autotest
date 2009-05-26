package autotest.tko;

import autotest.common.table.DataSource.DataCallback;
import autotest.common.ui.NotifyManager;
import autotest.tko.Spreadsheet.CellInfo;
import autotest.tko.Spreadsheet.Header;
import autotest.tko.Spreadsheet.HeaderImpl;

import com.google.gwt.core.client.Duration;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.DeferredCommand;
import com.google.gwt.user.client.IncrementalCommand;

import java.util.ArrayList;
import java.util.List;

public class SpreadsheetDataProcessor implements DataCallback {
    private static final NotifyManager notifyManager = NotifyManager.getInstance();
    private static final int MAX_CELL_COUNT = 500000;
    private static final int ROWS_PROCESSED_PER_ITERATION = 1000;
    
    private Spreadsheet spreadsheet;
    private TestGroupDataSource dataSource;
    private int numTotalTests;
    private CellInfo lastCellInfo;

    private Header rowFields, columnFields;
    private Command onFinished;
    private Duration timer;
    
    public static class TooManyCellsError extends Exception {
        public int cellCount;

        public TooManyCellsError(int cellCount) {
            super();
            this.cellCount = cellCount;
        }
    }
    
    private class ProcessDataCommand implements IncrementalCommand {
        private int state = 0;
        private JSONArray counts;
        private int currentRow = 0;
        
        public ProcessDataCommand(JSONArray counts) {
            this.counts = counts;
        }
        
        public void processSomeRows() {
            for (int i = 0; i < ROWS_PROCESSED_PER_ITERATION; i++, currentRow++) {
                if (currentRow == counts.size()) {
                    state++;
                    return;
                }
                processRow(counts.get(currentRow).isObject());
            }
        }
        
        public boolean execute() {
            switch (state) {
                case 0:
                    notifyManager.setLoading(true);
                    numTotalTests = 0;
                    try {
                        processHeaders();
                    } catch (TooManyCellsError exc) {
                        notifyManager.showError("Resulting spreadsheet contains " + exc.cellCount +
                                                " cells, " + "exceeding maximum " + MAX_CELL_COUNT);
                        finalizeCommand();
                        return false;
                    }
                    break;
                case 1:
                    spreadsheet.prepareForData();
                    break;
                case 2:
                    processSomeRows();
                    return true;
                case 3:
                    // we must make the spreadsheet visible before rendering, or size computations 
                    // won't work correctly
                    spreadsheet.setVisible(true);
                    break;
                case 4:
                    spreadsheet.render(this);
                    state++;
                    return false; // render will re-add us to the command queue
                case 5:
                    logTimer("Rendering");
                    finalizeCommand();
                    return false;
            }
            
            state++;
            return true;
        }

        private void finalizeCommand() {
            notifyManager.setLoading(false);
            onFinished.execute();
        }
    }
    
    public SpreadsheetDataProcessor(Spreadsheet spreadsheet) {
        this.spreadsheet = spreadsheet;
    }

    public void processHeaders() throws TooManyCellsError {
        spreadsheet.setHeaderFields(rowFields, columnFields);
        List<List<String>> rowHeaderValues = dataSource.getHeaderGroupValues(0);
        List<List<String>> columnHeaderValues = dataSource.getHeaderGroupValues(1);
        int totalCells = rowHeaderValues.size() * columnHeaderValues.size();
        if (totalCells > MAX_CELL_COUNT) {
            throw new TooManyCellsError(totalCells);
        }
        for (List<String> header : rowHeaderValues) {
            spreadsheet.addRowHeader(header);
        }
        for (List<String> header : columnHeaderValues) {
            spreadsheet.addColumnHeader(header);
        }
    }

    private void processRow(JSONObject group) {
        JSONArray headerIndices = group.get("header_indices").isArray();
        int row = (int) headerIndices.get(0).isNumber().doubleValue();
        int column = (int) headerIndices.get(1).isNumber().doubleValue();
        CellInfo cellInfo = spreadsheet.getCellInfo(row, column);
        StatusSummary statusSummary = StatusSummary.getStatusSummary(group);
        numTotalTests += statusSummary.getTotal();
        cellInfo.contents = statusSummary.formatContents();
        cellInfo.color = statusSummary.getColor();
        cellInfo.testCount = statusSummary.getTotal();
        cellInfo.testIndex = (int) group.get("test_idx").isNumber().doubleValue();
        lastCellInfo = cellInfo;
    }
    
    public void refresh(JSONObject condition, Command onFinished) {
        timer = new Duration();
        this.onFinished = onFinished;
        dataSource.updateData(condition, this);
    }
    
    public void onGotData(int totalCount) {
        dataSource.getPage(null, null, null, this);
    }

    public void handlePage(JSONArray data) {
        logTimer("Server response");
        if (data.size() == 0) {
            notifyManager.showMessage("No results for query");
            onFinished.execute();
            return;
        }

        DeferredCommand.addCommand(new ProcessDataCommand(data));
    }
    
    private void logTimer(String message) {
        notifyManager.log(message + ": " + timer.elapsedMillis() + " ms");
        timer = new Duration();
    }

    public int getNumTotalTests() {
        return numTotalTests;
    }
    
    /**
     * This is useful when there turns out to be only a single test return.
     * @return the last CellInfo created.  Should only really be called when there was only a single
     *         one.
     */
    public CellInfo getLastCellInfo() {
        assert numTotalTests == 1;
        return lastCellInfo;
    }
    
    public void onError(JSONObject errorObject) {
        onFinished.execute();
    }

    public void setHeaders(List<HeaderField> rowFields, List<HeaderField> columnFields, 
                           JSONObject queryParameters) {
        this.rowFields = getHeaderSqlNames(rowFields);
        this.columnFields = getHeaderSqlNames(columnFields);
        
        List<List<String>> headerGroups = new ArrayList<List<String>>();
        headerGroups.add(this.rowFields);
        headerGroups.add(this.columnFields);
        dataSource.setHeaderGroups(headerGroups);
        dataSource.setQueryParameters(queryParameters);
    }

    private Header getHeaderSqlNames(List<HeaderField> fields) {
        Header header = new HeaderImpl();
        for (HeaderField field : fields) {
            header.add(field.getSqlName());
        }
        return header;
    }

    public void setDataSource(TestGroupDataSource dataSource) {
        this.dataSource = dataSource;
    }

    public TestGroupDataSource getDataSource() {
        return dataSource;
    }
}

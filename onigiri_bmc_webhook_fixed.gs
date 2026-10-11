/**
 * ONIGIRI - MOTOR DE VENDAS (WEBHOOK DO BUY ME A COFFEE) - conta peacemonk
 * E-mail = "ticket" com ícone, mensagem de agradecimento, pills e código,
 * adaptado a light/dark mode. Log de execução em HTML, colorido por tipo
 * de evento.
 */

const SHEET_ID = '12DB4IJlw4f8GAWyk23kK0EUHm7hB8P0mHLzj4r2Vtz0';

// IDs dos ícones no Google Drive, um por família de produto.
const ICON_IDS = {
  coin: '1VhQc8Fq3Ra-edz62MrmfizJuExApNt1A',
  hex: '18u0wQClLwP-nAkelh1XgZWexWTCFNHaE',
  comet: '1TAO4KlnGHJJfmRusojN6rp7RdWl7ZIBp',
  star: '10N6-NrZF9QwCrvRulI7dzMvfhTqKmMbZ',
  item: '1ocBkxKZJq9Jgf0OBUFkFIoVAFP8pbgrA'
};

// Paleta por família: frame = moldura (cor-tema), pill = fundo claro das
// pílulas/badge, text = texto escuro sobre o fundo claro. O modo escuro
// reaproveita esses mesmos tons invertendo os papéis (pill vira o "text"
// claro escrito sobre um fundo escuro que é o antigo "text").
const THEME = {
  coin: { frame: '#F6C51A', pill: '#FBE28C', text: '#5F4E10' },
  hex: { frame: '#5CC8F1', pill: '#AEE4F8', text: '#154655' },
  comet: { frame: '#C5DEE6', pill: '#E2EFF3', text: '#33505C' },
  star: { frame: '#FFDEDE', pill: '#FFEEEE', text: '#8A4A4A' },
  item: { frame: '#6AD55A', pill: '#B4EAAC', text: '#204D1A' }
};

const CARD_BG_DARK = '#1c1c1c';
const SALES_LOG_SHEET = 'BMC Sales Log';
const SALES_LOG_HEADERS = [
  'Unit Key', 'Transaction ID', 'Event ID', 'Extra ID', 'Product', 'Unit',
  'Buyer Email', 'Code', 'Sheet', 'Sheet Row', 'Amount', 'Item Key',
  'Status', 'Updated At', 'Error'
];

function hexToRgb_(hex) {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.substring(0, 2), 16);
  const g = parseInt(clean.substring(2, 4), 16);
  const b = parseInt(clean.substring(4, 6), 16);
  return r + ',' + g + ',' + b;
}

// Monta o HTML completo do ticket. redeemSteps = array de 2-3 passos curtos
// de como resgatar ESSE tipo de produto dentro do Onigiri (varia por moeda/item).
function buildTicketEmail_(titleLine1, titleLine2, colors, redeemSteps) {
  const bgLight = colors.pill;   // fundo externo claro no light mode
  const bgDark = colors.text;    // fundo externo amarelo-queimado escuro no dark mode
  const pillDark = colors.text;
  const textDark = colors.pill;

  const stepsHtml = redeemSteps.map(function (step, i) {
    return (
      '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin-bottom:10px;">' +
        '<tr>' +
          '<td class="t-pill" style="width:26px; height:26px; border-radius:50%; text-align:center; vertical-align:middle; font-weight:700; font-size:13px;">' + (i + 1) + '</td>' +
          '<td class="t-message" style="padding-left:12px; font-size:14px; line-height:1.5; text-align:left;">' + step + '</td>' +
        '</tr>' +
      '</table>'
    );
  }).join('');

  return (
    '<!DOCTYPE html><html><head>' +
    '<meta name="color-scheme" content="light dark">' +
    '<meta name="supported-color-schemes" content="light dark">' +
    '<style>' +
      '.t-frame{background:' + bgLight + ';}' +
      '.t-pill{background:' + colors.pill + '; color:' + colors.text + ';}' +
      '.t-codebox{background:' + colors.pill + ';}' +
      '.t-codetext{color:' + colors.text + ';}' +
      '.t-divider{border-top:3px dashed ' + bgLight + ';}' +
      '.t-title,.t-message{color:#1a1a1a;}' +
      '.t-card{background:#ffffff;}' +
      '@media (prefers-color-scheme: dark) {' +
        '.t-frame{background:' + bgDark + ' !important;}' +
        '.t-card{background:' + CARD_BG_DARK + ' !important;}' +
        '.t-pill{background:' + pillDark + ' !important; color:' + textDark + ' !important;}' +
        '.t-codebox{background:' + pillDark + ' !important;}' +
        '.t-codetext{color:' + textDark + ' !important;}' +
        '.t-divider{border-top-color:' + bgDark + ' !important;}' +
        '.t-title,.t-message{color:#f0f0f0 !important;}' +
      '}' +
    '</style></head><body style="margin:0; padding:0;">' +
    '<div class="t-frame" style="background:' + bgLight + '; padding:32px; font-family:\'Montserrat\', Verdana, Arial, sans-serif;">' +
      '<div class="t-card" style="background:#ffffff; border-radius:24px; overflow:hidden; max-width:460px; margin:0 auto;">' +
        '<div style="padding:32px 32px 22px;">' +
          '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">' +
            '<tr>' +
              '<td style="width:72px; vertical-align:middle;">' +
                '<img src="cid:productIcon" width="72" style="width:72px; height:auto; display:block;" />' +
              '</td>' +
              '<td class="t-title" style="vertical-align:middle; padding-left:10px; font-size:26px; line-height:1.15; font-weight:700;">' +
                titleLine1 + '<br/>' + titleLine2 +
              '</td>' +
            '</tr>' +
          '</table>' +
          '<p class="t-message" style="font-size:15px; line-height:1.6; margin:12px 0 20px; text-align:justify;">' +
            'From the bottom of my heart, thank you. Every code you claim is what keeps Onigiri alive and growing. ' +
            'This little world exists because of people like you, and I am truly grateful to have you in it.' +
          '</p>' +
          '<div style="text-align:left; max-width:320px; margin:0 auto;">' +
            stepsHtml +
          '</div>' +
        '</div>' +
        '<div class="t-divider" style="border-top:3px dashed ' + bgLight + ';"></div>' +
        '<div style="padding:26px 32px 34px; text-align:center;">' +
          '<div class="t-codebox" style="background:' + colors.pill + '; border-radius:18px; padding:20px 24px;">' +
            '<div class="t-codetext" style="font-family:\'Courier New\', monospace; font-size:17px; font-weight:700; letter-spacing:1px; color:' + colors.text + '; text-align:center; white-space:nowrap;">{{code}}</div>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>' +
    '</body></html>'
  );
}

// Passos de resgate por família. O do Taiyaki já está preenchido; os outros
// quatro precisam ser confirmados por quem conhece a navegação real do app.
const REDEEM_STEPS = {
  coin: ['Open the Taiyaki Store', 'Tap Get More Coins', 'Enter your code and redeem'],
  hex: ['Open Hexagon Land', 'Tap the + button', 'Enter your code and redeem'],
  comet: ['Open Onigimon', 'Tap Redeem', 'Enter your code and redeem'],
  star: ['Open Onigimon', 'Tap Redeem', 'Enter your code and redeem'],
  item: ['Open Onigimon', 'Tap Redeem', 'Enter your code and redeem']
};

const TICKET_COIN = buildTicketEmail_('Coin', 'Ticket', THEME.coin, REDEEM_STEPS.coin);
const TICKET_HEX = buildTicketEmail_('Hex', 'Ticket', THEME.hex, REDEEM_STEPS.hex);
const TICKET_COMET = buildTicketEmail_('Comet', 'Ticket', THEME.comet, REDEEM_STEPS.comet);
const TICKET_STAR = buildTicketEmail_('Star', 'Ticket', THEME.star, REDEEM_STEPS.star);
const TICKET_ITEM = buildTicketEmail_('Surprise', 'Ticket', THEME.item, REDEEM_STEPS.item);

const SALES_CONFIG = {
  // ---------- TAIYAKI COINS ----------
  'Taiyaki Coins - 5000': {
    type: 'simple', sheetName: 'Taiyaki Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, soldToColumn: 4, soldAtColumn: 5,
    amountFilter: 5000,
    imageFileId: ICON_IDS.coin,
    emailSubject: 'Your {{amount}} Taiyaki Coins have arrived!',
    emailBody: TICKET_COIN
  },
  'Taiyaki Coins - 10000': {
    type: 'simple', sheetName: 'Taiyaki Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, soldToColumn: 4, soldAtColumn: 5,
    amountFilter: 10000,
    imageFileId: ICON_IDS.coin,
    emailSubject: 'Your {{amount}} Taiyaki Coins have arrived!',
    emailBody: TICKET_COIN
  },
  'Taiyaki Coins - 15000': {
    type: 'simple', sheetName: 'Taiyaki Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, soldToColumn: 4, soldAtColumn: 5,
    amountFilter: 15000,
    imageFileId: ICON_IDS.coin,
    emailSubject: 'Your {{amount}} Taiyaki Coins have arrived!',
    emailBody: TICKET_COIN
  },

  // ---------- HEX COINS ----------
  'Hex Coins - 500': {
    type: 'simple', sheetName: 'Hex Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, soldToColumn: 4, soldAtColumn: 5,
    amountFilter: 500,
    imageFileId: ICON_IDS.hex,
    emailSubject: 'Your {{amount}} Hex Coins have arrived!',
    emailBody: TICKET_HEX
  },
  'Hex Coins - 1000': {
    type: 'simple', sheetName: 'Hex Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, soldToColumn: 4, soldAtColumn: 5,
    amountFilter: 1000,
    imageFileId: ICON_IDS.hex,
    emailSubject: 'Your {{amount}} Hex Coins have arrived!',
    emailBody: TICKET_HEX
  },
  'Hex Coins - 1500': {
    type: 'simple', sheetName: 'Hex Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, soldToColumn: 4, soldAtColumn: 5,
    amountFilter: 1500,
    imageFileId: ICON_IDS.hex,
    emailSubject: 'Your {{amount}} Hex Coins have arrived!',
    emailBody: TICKET_HEX
  },

  // ---------- COMET SHARDS ----------
  'Onigimon Coins - Comet Shards - 500': {
    type: 'currency', sheetName: 'Onigimon Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, currencyColumn: 4,
    currencyFilter: 'comet_shards', amountFilter: 500, soldToColumn: 5, soldAtColumn: 6,
    imageFileId: ICON_IDS.comet,
    emailSubject: 'Your {{amount}} Comet Shards have arrived!',
    emailBody: TICKET_COMET
  },
  'Onigimon Coins - Comet Shards - 1000': {
    type: 'currency', sheetName: 'Onigimon Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, currencyColumn: 4,
    currencyFilter: 'comet_shards', amountFilter: 1000, soldToColumn: 5, soldAtColumn: 6,
    imageFileId: ICON_IDS.comet,
    emailSubject: 'Your {{amount}} Comet Shards have arrived!',
    emailBody: TICKET_COMET
  },
  'Onigimon Coins - Comet Shards - 1500': {
    type: 'currency', sheetName: 'Onigimon Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, currencyColumn: 4,
    currencyFilter: 'comet_shards', amountFilter: 1500, soldToColumn: 5, soldAtColumn: 6,
    imageFileId: ICON_IDS.comet,
    emailSubject: 'Your {{amount}} Comet Shards have arrived!',
    emailBody: TICKET_COMET
  },

  // ---------- STAR PIECES ----------
  'Onigimon Coins - Star Pieces - 250': {
    type: 'currency', sheetName: 'Onigimon Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, currencyColumn: 4,
    currencyFilter: 'star_pieces', amountFilter: 250, soldToColumn: 5, soldAtColumn: 6,
    imageFileId: ICON_IDS.star,
    emailSubject: 'Your {{amount}} Star Pieces have arrived!',
    emailBody: TICKET_STAR
  },
  'Onigimon Coins - Star Pieces - 500': {
    type: 'currency', sheetName: 'Onigimon Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, currencyColumn: 4,
    currencyFilter: 'star_pieces', amountFilter: 500, soldToColumn: 5, soldAtColumn: 6,
    imageFileId: ICON_IDS.star,
    emailSubject: 'Your {{amount}} Star Pieces have arrived!',
    emailBody: TICKET_STAR
  },
  'Onigimon Coins - Star Pieces - 1000': {
    type: 'currency', sheetName: 'Onigimon Coins',
    codeColumn: 1, amountColumn: 2, statusColumn: 3, currencyColumn: 4,
    currencyFilter: 'star_pieces', amountFilter: 1000, soldToColumn: 5, soldAtColumn: 6,
    imageFileId: ICON_IDS.star,
    emailSubject: 'Your {{amount}} Star Pieces have arrived!',
    emailBody: TICKET_STAR
  },

  // ---------- SURPRISE PACK / ITEMS ----------
  'Onigimon Items - Surprise Pack - 10': {
    type: 'random_item', sheetName: 'Onigimon Items',
    codeColumn: 1, itemKeyColumn: 2, amountColumn: 3, statusColumn: 4,
    soldToColumn: 5, soldAtColumn: 6, amountFilter: 10,
    imageFileId: ICON_IDS.item,
    emailSubject: 'Your Surprise Pack has arrived!',
    emailBody: TICKET_ITEM
  },
  'Onigimon Items - Surprise Pack - 50': {
    type: 'random_item', sheetName: 'Onigimon Items',
    codeColumn: 1, itemKeyColumn: 2, amountColumn: 3, statusColumn: 4,
    soldToColumn: 5, soldAtColumn: 6, amountFilter: 50,
    imageFileId: ICON_IDS.item,
    emailSubject: 'Your Surprise Pack has arrived!',
    emailBody: TICKET_ITEM
  },
  'Onigimon Items - Surprise Pack - 100': {
    type: 'random_item', sheetName: 'Onigimon Items',
    codeColumn: 1, itemKeyColumn: 2, amountColumn: 3, statusColumn: 4,
    soldToColumn: 5, soldAtColumn: 6, amountFilter: 100,
    imageFileId: ICON_IDS.item,
    emailSubject: 'Your Surprise Pack has arrived!',
    emailBody: TICKET_ITEM
  }
};

function generateWebhookToken() {
  const token = Utilities.getUuid();
  PropertiesService.getScriptProperties().setProperty('WEBHOOK_TOKEN', token);
  Logger.log('Seu token: ' + token);
}

function doPost(e) {
  var diario = [];
  function reg(msg) { Logger.log(msg); diario.push(String(msg)); }

  if (!e || !e.postData) {
    reg('doPost sem evento válido (Run manual). Ignorando.');
    enviarDiario_(diario);
    return ContentService.createTextOutput('no event');
  }

  const expectedToken = PropertiesService.getScriptProperties().getProperty('WEBHOOK_TOKEN');
  const providedToken = e.parameter && e.parameter.token;

  if (!expectedToken || providedToken !== expectedToken) {
    reg('Token inválido. O valor recebido não será registrado por segurança.');
    enviarDiario_(diario);
    return ContentService.createTextOutput('invalid token');
  }

  let payload;

  try {
    payload = JSON.parse(e.postData.contents || '{}');
  } catch (error) {
    reg('ERRO: corpo JSON inválido: ' + error);
    enviarDiario_(diario);
    return ContentService.createTextOutput('invalid json');
  }

  reg('Evento recebido: ' + payload.type);

  if (payload.type !== 'extra_purchase.created') {
    reg('Tipo diferente de extra_purchase.created. Saindo (ignored).');
    enviarDiario_(diario);
    return ContentService.createTextOutput('ignored');
  }

  // Eventos enviados pelo botão de teste do BMC nunca devem consumir estoque.
  if (payload.live_mode === false) {
    reg('Evento de teste reconhecido. Nenhum código foi reservado ou enviado.');
    enviarDiario_(diario);
    return ContentService.createTextOutput('test ok');
  }

  const data = payload.data || {};
  const buyerEmail = String(data.supporter_email || '').trim();
  const extras = Array.isArray(data.extras) ? data.extras : [];

  if (!buyerEmail || buyerEmail.indexOf('@') < 1) {
    reg('ERRO: evento sem e-mail válido do comprador.');
    enviarDiario_(diario);
    notifyAdmin_('Compra recebida sem e-mail válido. Event ID: ' + escapeHtml_(payload.event_id));
    return ContentService.createTextOutput('missing buyer email');
  }

  if (!extras.length) {
    reg('ERRO: evento sem produtos em data.extras.');
    enviarDiario_(diario);
    notifyAdmin_('Compra sem produtos em data.extras. Event ID: ' + escapeHtml_(payload.event_id));
    return ContentService.createTextOutput('missing extras');
  }

  const orderKey = String(data.transaction_id || data.id || payload.event_id || '').trim();

  if (!orderKey) {
    reg('ERRO: evento sem identificador de transação.');
    enviarDiario_(diario);
    notifyAdmin_('Compra sem transaction_id, data.id ou event_id.');
    return ContentService.createTextOutput('missing transaction id');
  }

  const units = [];
  const unmapped = [];

  extras.forEach(function (extra, extraIndex) {
    const rawTitle = extra && extra.title;
    const productTitle = rawTitle ? sanitizeTitle_(rawTitle) : '';
    const config = SALES_CONFIG[productTitle];
    const parsedQuantity = Number(extra && extra.quantity);
    const quantity = Number.isFinite(parsedQuantity) && parsedQuantity > 0
      ? Math.floor(parsedQuantity)
      : 1;

    reg('Produto ' + (extraIndex + 1) + ': "' + productTitle + '" x' + quantity);

    if (!config) {
      unmapped.push(productTitle || '(sem título)');
      return;
    }

    for (let unitNumber = 1; unitNumber <= quantity; unitNumber += 1) {
      const extraKey = String(extra.id || ('index-' + extraIndex));
      units.push({
        unitKey: orderKey + '|' + extraKey + '|' + unitNumber,
        transactionId: String(data.transaction_id || data.id || ''),
        eventId: String(payload.event_id || ''),
        extraId: String(extra.id || ''),
        productTitle: productTitle,
        unitNumber: unitNumber,
        config: config
      });
    }
  });

  if (unmapped.length) {
    reg('ERRO: produtos sem correspondência: ' + unmapped.join(', '));
    enviarDiario_(diario);
    notifyAdmin_(
      'Compra não processada porque há produtos sem correspondência: ' +
      escapeHtml_(unmapped.join(', ')) + '. Transação: ' + escapeHtml_(orderKey)
    );
    return ContentService.createTextOutput('unmapped product');
  }

  reg('buyerEmail: ' + buyerEmail);
  reg('Unidades a processar: ' + units.length);

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);

  try {
    const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    const reservations = reserveOrder_(spreadsheet, units, buyerEmail, reg);
    const failures = [];

    reservations.forEach(function (reservation) {
      if (reservation.status === 'SENT') {
        reg('Unidade já entregue anteriormente: ' + reservation.unitKey);
        return;
      }

      const emailOk = sendCodeEmail_(
        buyerEmail,
        reservation.productTitle,
        reservation.code,
        reservation.amount,
        reservation.itemKey,
        reservation.config,
        reg
      );

      updateSaleLogStatus_(
        reservation.logSheet,
        reservation.logRow,
        emailOk ? 'SENT' : 'EMAIL_FAILED',
        emailOk ? '' : 'GmailApp.sendEmail failed'
      );

      if (emailOk) {
        reg('ENTREGUE: ' + reservation.productTitle + ' (' + reservation.unitNumber + ')');
      } else {
        failures.push(reservation.productTitle + ' (' + reservation.unitNumber + ')');
      }
    });

    SpreadsheetApp.flush();

    if (failures.length) {
      reg('FALHA: ' + failures.length + ' unidade(s) não enviada(s).');
      throw new Error(
        'Falha de e-mail em: ' + failures.join(', ') +
        '. Os códigos continuam reservados para o comprador.'
      );
    }
  } catch (error) {
    reg('ERRO ao processar o pedido: ' + error);
    notifyAdmin_(
      'Erro na transação ' + escapeHtml_(orderKey) + ': ' + escapeHtml_(error)
    );
    enviarDiario_(diario);
    throw error;
  } finally {
    try {
      SpreadsheetApp.flush();
    } finally {
      lock.releaseLock();
    }
  }

  enviarDiario_(diario);
  return ContentService.createTextOutput('ok');
}

function reserveOrder_(spreadsheet, units, buyerEmail, reg) {
  const logSheet = getSalesLogSheet_(spreadsheet);
  const existing = readSalesLog_(logSheet);
  const inventory = {};
  const reservations = [];
  const newReservations = [];
  const now = new Date();

  // Primeiro planeja o pedido inteiro. Se qualquer produto estiver sem estoque,
  // nenhum código novo será reservado e nenhum e-mail será enviado.
  units.forEach(function (unit) {
    const previous = existing[unit.unitKey];

    if (previous) {
      if (previous.buyerEmail && previous.buyerEmail !== buyerEmail) {
        throw new Error('Unit key already belongs to another buyer: ' + unit.unitKey);
      }

      reservations.push({
        unitKey: unit.unitKey,
        unitNumber: unit.unitNumber,
        productTitle: unit.productTitle,
        config: unit.config,
        code: previous.code,
        amount: previous.amount,
        itemKey: previous.itemKey,
        status: previous.status,
        logSheet: logSheet,
        logRow: previous.logRow
      });
      return;
    }

    const stock = getInventory_(spreadsheet, unit.config.sheetName, inventory);
    const rowIndex = chooseStockRow_(stock.data, unit.config);

    if (rowIndex < 0) {
      throw new Error('No stock for "' + unit.productTitle + '"');
    }

    const row = stock.data[rowIndex];
    const reservation = {
      unitKey: unit.unitKey,
      transactionId: unit.transactionId,
      eventId: unit.eventId,
      extraId: unit.extraId,
      unitNumber: unit.unitNumber,
      productTitle: unit.productTitle,
      config: unit.config,
      code: String(row[unit.config.codeColumn - 1] || '').trim(),
      amount: row[unit.config.amountColumn - 1],
      itemKey: unit.config.itemKeyColumn
        ? String(row[unit.config.itemKeyColumn - 1] || '').trim()
        : '',
      status: 'RESERVED',
      sheet: stock.sheet,
      sheetRow: rowIndex + 1,
      logSheet: logSheet,
      logRow: 0
    };

    if (!reservation.code) {
      throw new Error('Blank code found for "' + unit.productTitle + '"');
    }

    // Impede que outra unidade deste mesmo pedido reutilize a linha planejada.
    row[unit.config.soldToColumn - 1] = buyerEmail;
    row[unit.config.soldAtColumn - 1] = now;
    reservations.push(reservation);
    newReservations.push(reservation);
  });

  newReservations.forEach(function (reservation) {
    reservation.sheet
      .getRange(reservation.sheetRow, reservation.config.soldToColumn, 1, 2)
      .setValues([[buyerEmail, now]]);
    reg('Reservado: ' + reservation.productTitle + ' -> ' + reservation.code);
  });

  if (newReservations.length) {
    const firstLogRow = logSheet.getLastRow() + 1;
    const logRows = newReservations.map(function (reservation) {
      return [
        reservation.unitKey,
        reservation.transactionId,
        reservation.eventId,
        reservation.extraId,
        reservation.productTitle,
        reservation.unitNumber,
        buyerEmail,
        reservation.code,
        reservation.config.sheetName,
        reservation.sheetRow,
        reservation.amount,
        reservation.itemKey,
        'RESERVED',
        now,
        ''
      ];
    });

    logSheet.getRange(firstLogRow, 1, logRows.length, SALES_LOG_HEADERS.length)
      .setValues(logRows);

    newReservations.forEach(function (reservation, index) {
      reservation.logRow = firstLogRow + index;
    });
  }

  SpreadsheetApp.flush();
  return reservations;
}

function getInventory_(spreadsheet, sheetName, inventory) {
  if (inventory[sheetName]) {
    return inventory[sheetName];
  }

  const sheet = spreadsheet.getSheetByName(sheetName);

  if (!sheet) {
    throw new Error('Sheet not found: ' + sheetName);
  }

  inventory[sheetName] = {
    sheet: sheet,
    data: sheet.getDataRange().getValues()
  };
  return inventory[sheetName];
}

function chooseStockRow_(data, config) {
  const candidates = [];

  for (let i = 1; i < data.length; i += 1) {
    const row = data[i];
    const status = String(row[config.statusColumn - 1] || '').trim().toLowerCase();
    const soldTo = row[config.soldToColumn - 1];

    if (status !== 'active' || soldTo) continue;

    if (config.currencyFilter) {
      const currency = String(row[config.currencyColumn - 1] || '').trim().toLowerCase();
      if (currency !== config.currencyFilter) continue;
    }

    if (config.itemKeyFilter) {
      const itemKey = String(row[config.itemKeyColumn - 1] || '').trim();
      if (itemKey !== config.itemKeyFilter) continue;
    }

    if (config.amountFilter !== undefined) {
      const amount = Number(row[config.amountColumn - 1] || 0);
      if (amount !== config.amountFilter) continue;
    }

    candidates.push(i);
  }

  if (!candidates.length) return -1;
  return config.type === 'random_item'
    ? candidates[Math.floor(Math.random() * candidates.length)]
    : candidates[0];
}

function getSalesLogSheet_(spreadsheet) {
  let sheet = spreadsheet.getSheetByName(SALES_LOG_SHEET);

  if (!sheet) {
    sheet = spreadsheet.insertSheet(SALES_LOG_SHEET);
  }

  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, SALES_LOG_HEADERS.length).setValues([SALES_LOG_HEADERS]);
    sheet.setFrozenRows(1);
  }

  return sheet;
}

function readSalesLog_(sheet) {
  const result = {};

  if (sheet.getLastRow() < 2) return result;

  const rows = sheet
    .getRange(2, 1, sheet.getLastRow() - 1, SALES_LOG_HEADERS.length)
    .getValues();

  rows.forEach(function (row, index) {
    const unitKey = String(row[0] || '');

    if (!unitKey) return;

    result[unitKey] = {
      buyerEmail: String(row[6] || ''),
      code: String(row[7] || ''),
      amount: row[10],
      itemKey: String(row[11] || ''),
      status: String(row[12] || 'RESERVED'),
      logRow: index + 2
    };
  });

  return result;
}

function updateSaleLogStatus_(sheet, row, status, errorMessage) {
  sheet.getRange(row, 13, 1, 3).setValues([[
    status,
    new Date(),
    String(errorMessage || '')
  ]]);
}

function sendCodeEmail_(buyerEmail, productTitle, code, amount, itemKey, config, reg) {
  reg = reg || function(){};
  const details = itemKey ? (itemKey + (amount > 1 ? ' x' + amount : '')) : String(amount);

  const subjectTemplate = config.emailSubject || ('Your Onigiri code - ' + productTitle);
  const bodyTemplate = config.emailBody ||
    'Your code: <b>{{code}}</b><br>Contents: {{details}}';

  const subject = applyPlaceholders_(subjectTemplate, code, amount, details, productTitle, itemKey);
  let body = applyPlaceholders_(bodyTemplate, code, amount, details, productTitle, itemKey);

  if (config.imageFileId) {
    const iconUrl = 'https://lh3.googleusercontent.com/d/' + config.imageFileId;
    body = body.replace(/cid:productIcon/g, iconUrl);
    reg('Ícone referenciado via URL pública: ' + iconUrl);
  } else {
    body = body.replace(/<img[^>]*src="cid:productIcon"[^>]*>/gi, '');
  }

  try {
    GmailApp.sendEmail(buyerEmail, subject, stripHtml_(body), {
      htmlBody: body,
      bcc: Session.getEffectiveUser().getEmail()
    });
    reg('E-mail enviado para ' + buyerEmail + ' (cópia em bcc para você)');
    return true;
  } catch (err2) {
    reg('Envio do e-mail falhou: ' + err2);
    return false;
  }
}

function applyPlaceholders_(text, code, amount, details, productTitle, itemKey) {
  return String(text)
    .replace(/{{code}}/g, code)
    .replace(/{{amount}}/g, amount)
    .replace(/{{details}}/g, details)
    .replace(/{{productTitle}}/g, productTitle)
    .replace(/{{itemKey}}/g, itemKey || '');
}

function sanitizeTitle_(title) {
  return String(title)
    .replace(/[\u200B-\u200F\u202A-\u202E\uFEFF]/g, '')
    .replace(/\u00A0/g, ' ')
    .trim();
}

function stripHtml_(html) {
  return String(html)
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function enviarDiario_(diario) {
  try {
    const linhas = diario.map(function (msg) {
      const texto = String(msg);
      let cor = '#5a5a5a';
      let fundo = '#f5f5f5';

      if (/ERRO|FALHA|inválido|não encontrada|NÃO entregue|NÃO enviado/i.test(texto)) {
        cor = '#B3261E';
        fundo = '#FDECEA';
      } else if (/ENTREGUE|enviado COM imagem|enviado SEM imagem|ENCONTRADO/i.test(texto)) {
        cor = '#1B7A3D';
        fundo = '#E9F6EC';
      }

      return (
        '<div style="background:' + fundo + '; border-left: 3px solid ' + cor + '; ' +
        'padding: 8px 12px; margin-bottom: 6px; border-radius: 4px; ' +
        'font-family: \'Courier New\', monospace; font-size: 13px; color: ' + cor + ';">' +
          escapeHtml_(texto) +
        '</div>'
      );
    }).join('');

    const html =
      '<div style="font-family: Arial, Helvetica, sans-serif; max-width: 600px; margin: 0 auto;">' +
        '<h2 style="font-size: 17px; margin: 0 0 2px; color: #1a1a1a;">Onigiri — Log de execução</h2>' +
        '<p style="font-size: 13px; color: #888; margin: 0 0 18px;">' + new Date().toLocaleString() + '</p>' +
        linhas +
      '</div>';

    MailApp.sendEmail({
      to: Session.getEffectiveUser().getEmail(),
      subject: 'Onigiri LOG - ' + new Date().toLocaleString(),
      htmlBody: html
    });
  } catch (err) {
    Logger.log('Não consegui enviar o diário: ' + err);
  }
}

function escapeHtml_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function notifyAdmin_(message) {
  MailApp.sendEmail({
    to: Session.getEffectiveUser().getEmail(),
    subject: 'Onigiri - atenção necessária',
    htmlBody: message
  });
}
